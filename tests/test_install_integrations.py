import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
HELPER = SCRIPTS / "install_integrations.py"


def integration_tool(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("install_integrations", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installation(tmp_path):
    project = tmp_path / "Chopper folder ' $cash %literal"
    project.mkdir()
    launcher = project / "chopper"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    return launcher, tmp_path / "home", tmp_path / "data"


def cli(installation, *, answers="", initial_path="/usr/bin:/bin", path=None):
    launcher, home, data = installation
    return subprocess.run(
        [sys.executable, str(HELPER), "--launcher", str(launcher), "--initial-path", initial_path],
        input=answers,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env={**os.environ, "HOME": str(home), "XDG_DATA_HOME": str(data), "PATH": path or initial_path},
    )


@pytest.mark.parametrize("answers", ["", "\n\n", "n\nn\n"])
def test_declining_all_integrations_creates_no_home_or_receipt(installation, answers):
    launcher, home, data = installation
    result = cli(installation, answers=answers)
    assert result.returncode == 0, result.stderr
    assert not home.exists() and not data.exists()
    assert not (launcher.parent / ".chopper-install.json").exists()
    assert str(home / ".local/bin/chopper") in result.stdout
    assert "skipped" in result.stdout.lower()


def test_link_receipt_records_identity_and_reinstall_is_idempotent(installation, monkeypatch):
    launcher, home, _ = installation
    tool = integration_tool(monkeypatch)
    destination = tool.install_global_command(launcher, home=home)
    assert destination == home / ".local/bin/chopper" and destination.is_symlink()
    assert os.readlink(destination) == str(launcher)
    receipt_path = launcher.parent / ".chopper-install.json"
    before = receipt_path.read_bytes()
    before_stat = destination.lstat()
    receipt = tool.load_receipt(launcher.parent)
    assert receipt["schema_version"] == 1 and receipt["project"] == str(launcher.parent)
    artifact = receipt["artifacts"]["global-command"]
    assert artifact["path"] == str(destination) and artifact["target"] == str(launcher)
    assert artifact["inode"] == before_stat.st_ino and artifact["device"] == before_stat.st_dev
    assert tool.install_global_command(launcher, home=home) == destination
    assert receipt_path.read_bytes() == before and destination.lstat() == before_stat


@pytest.mark.parametrize("kind", ["file", "directory", "foreign-link", "broken-link", "same-target-unowned"])
def test_unowned_global_destination_is_never_overwritten(installation, tmp_path, monkeypatch, kind):
    launcher, home, _ = installation
    destination = home / ".local/bin/chopper"
    destination.parent.mkdir(parents=True)
    other = tmp_path / "foreign"
    other.write_text("foreign sentinel")
    if kind == "file":
        destination.write_text("foreign sentinel")
    elif kind == "directory":
        destination.mkdir()
    else:
        target = (
            launcher
            if kind == "same-target-unowned"
            else other
            if kind == "foreign-link"
            else tmp_path / "missing"
        )
        destination.symlink_to(target)
    original = destination.lstat()
    tool = integration_tool(monkeypatch)
    with pytest.raises((OSError, ValueError)):
        tool.install_global_command(launcher, home=home)
    assert destination.lstat() == original and other.read_text() == "foreign sentinel"
    assert not (launcher.parent / ".chopper-install.json").exists()


def test_recreated_identical_link_is_no_longer_owned(installation, tmp_path, monkeypatch):
    launcher, home, _ = installation
    tool = integration_tool(monkeypatch)
    destination = tool.install_global_command(launcher, home=home)
    # Keep the old inode alive, so the replacement identity is unambiguously new.
    destination.rename(tmp_path / "original-link")
    destination.symlink_to(launcher)
    replacement = destination.lstat()
    with pytest.raises((OSError, ValueError)):
        tool.install_global_command(launcher, home=home)
    assert destination.lstat() == replacement and os.readlink(destination) == str(launcher)


@pytest.mark.parametrize("kind", ["invalid-json", "wrong-project", "wrong-version", "symlink", "directory"])
def test_foreign_or_invalid_receipt_is_preserved_before_creating_link(
    installation, tmp_path, monkeypatch, kind
):
    launcher, home, _ = installation
    receipt = launcher.parent / ".chopper-install.json"
    if kind == "invalid-json":
        receipt.write_text("foreign sentinel")
    elif kind == "wrong-project":
        receipt.write_text(json.dumps({"schema_version": 1, "project": str(tmp_path), "artifacts": {}}))
    elif kind == "wrong-version":
        receipt.write_text(
            json.dumps({"schema_version": True, "project": str(launcher.parent), "artifacts": {}})
        )
    elif kind == "directory":
        receipt.mkdir()
    else:
        target = tmp_path / "foreign.json"
        target.write_text("foreign sentinel")
        receipt.symlink_to(target)
    original = receipt.lstat()
    tool = integration_tool(monkeypatch)
    with pytest.raises((OSError, ValueError)):
        tool.install_global_command(launcher, home=home)
    assert receipt.lstat() == original and not home.exists()


def test_receipt_write_failure_rolls_back_only_created_link(installation, monkeypatch):
    launcher, home, _ = installation
    tool = integration_tool(monkeypatch)

    real_link = tool.os.link

    def failure(source, destination, **kwargs):
        if Path(destination) == launcher.parent / ".chopper-install.json":
            raise PermissionError("receipt disk full")
        return real_link(source, destination, **kwargs)

    monkeypatch.setattr(tool.os, "link", failure)
    with pytest.raises(OSError, match="receipt disk full"):
        tool.install_global_command(launcher, home=home)
    assert not (home / ".local/bin/chopper").is_symlink()
    assert not (launcher.parent / ".chopper-install.json").exists()
    assert list(launcher.parent.iterdir()) == [launcher]


def test_receipt_collision_during_publish_does_not_overwrite_foreign_file(installation, monkeypatch):
    launcher, home, _ = installation
    tool = integration_tool(monkeypatch)
    receipt = launcher.parent / ".chopper-install.json"

    real_link = tool.os.link

    def occupied(source, destination, **kwargs):
        if Path(destination) == receipt:
            receipt.write_text("foreign concurrent sentinel")
            raise FileExistsError("receipt appeared concurrently")
        return real_link(source, destination, **kwargs)

    monkeypatch.setattr(tool.os, "link", occupied)
    with pytest.raises(OSError):
        tool.install_global_command(launcher, home=home)
    assert receipt.read_text() == "foreign concurrent sentinel"
    assert not (home / ".local/bin/chopper").is_symlink()


def test_initial_path_warning_is_not_hidden_by_current_process_path(installation):
    launcher, home, _ = installation
    result = cli(installation, answers="n\ny\n", path=f"{home}/.local/bin:/usr/bin:/bin")
    assert result.returncode == 0, result.stderr
    assert "not in the initial PATH" in result.stdout
    assert 'export PATH="$HOME/.local/bin:$PATH"' in result.stdout
    assert str(launcher.parent / ".chopper-install.json") in result.stdout


def test_existing_path_and_shadowed_command_are_reported(installation, tmp_path):
    _, home, _ = installation
    tools = tmp_path / "tools"
    tools.mkdir()
    foreign = tools / "chopper"
    foreign.write_text("#!/bin/sh\nexit 0\n")
    foreign.chmod(0o755)
    path = f"{tools}:{home}/.local/bin:/usr/bin:/bin"
    result = cli(installation, answers="n\ny\n", initial_path=path)
    assert result.returncode == 0, result.stderr
    assert "shadow" in result.stdout.lower() and str(foreign) in result.stdout
    assert "not in the initial PATH" not in result.stdout


def test_legacy_menu_adoption_tolerates_access_time_updates(installation):
    launcher, _, data = installation
    # Let the existing helper create the exact historical entry first.
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "install_desktop.py"), "--launcher", str(launcher)],
        input="y\n",
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
        env={**os.environ, "XDG_DATA_HOME": str(data)},
    )
    assert result.returncode == 0, result.stderr
    entry = data / "applications/chopper.desktop"
    before = entry.read_bytes()
    status = entry.stat()
    os.utime(entry, ns=(1, status.st_mtime_ns))
    result = cli(installation, answers="y\nn\n")
    assert result.returncode == 0, result.stderr
    assert entry.read_bytes() == before
    assert (launcher.parent / ".chopper-install.json").is_file()


@pytest.mark.parametrize("legacy", [False, True])
def test_menu_receipt_failure_removes_only_new_entry(installation, monkeypatch, legacy):
    launcher, _, data = installation
    tool = integration_tool(monkeypatch)
    entry = data / "applications/chopper.desktop"
    if legacy:
        entry.parent.mkdir(parents=True)
        entry.write_text(tool.desktop_entry(launcher))
        entry.chmod(0o644)
        before = entry.read_bytes()

    def failure(*args, **kwargs):
        raise PermissionError("receipt disk full")

    monkeypatch.setattr(tool, "_save_receipt", failure)
    with pytest.raises(OSError, match="receipt disk full"):
        tool._install_menu(launcher, data)
    assert entry.exists() is legacy
    if legacy:
        assert entry.read_bytes() == before


def test_concurrent_link_replacement_is_not_recorded_or_removed(installation, tmp_path, monkeypatch):
    launcher, home, _ = installation
    destination = home / ".local/bin/chopper"
    foreign = tmp_path / "foreign-launcher"
    foreign.write_text("foreign sentinel")
    tool = integration_tool(monkeypatch)
    real_symlink = Path.symlink_to
    real_link = tool.os.link

    def replace_with_foreign():
        destination.unlink()
        real_symlink(destination, foreign)

    def symlink_then_replace(path, target, **kwargs):
        real_symlink(path, target, **kwargs)
        if path == destination:
            replace_with_foreign()

    def link_then_replace(source, target, **kwargs):
        real_link(source, target, **kwargs)
        if Path(target) == destination:
            replace_with_foreign()

    monkeypatch.setattr(Path, "symlink_to", symlink_then_replace)
    monkeypatch.setattr(tool.os, "link", link_then_replace)
    with pytest.raises((OSError, ValueError)):
        tool.install_global_command(launcher, home=home)
    assert destination.is_symlink() and os.readlink(destination) == str(foreign)
    assert foreign.read_text() == "foreign sentinel"
    assert not (launcher.parent / ".chopper-install.json").exists()


def test_concurrent_menu_replacement_is_not_recorded_or_removed(installation, monkeypatch):
    launcher, _, data = installation
    destination = data / "applications/chopper.desktop"
    tool = integration_tool(monkeypatch)
    real_link = tool.os.link

    def link_then_replace(source, target, **kwargs):
        real_link(source, target, **kwargs)
        if Path(target) == destination:
            destination.unlink()
            destination.write_text("foreign concurrent menu sentinel")

    monkeypatch.setattr(tool.os, "link", link_then_replace)
    with pytest.raises((OSError, ValueError)):
        tool._install_menu(launcher, data)
    assert destination.read_text() == "foreign concurrent menu sentinel"
    assert not (launcher.parent / ".chopper-install.json").exists()


def test_concurrent_project_installation_is_refused_without_writes(installation, monkeypatch):
    import fcntl

    launcher, home, _ = installation
    tool = integration_tool(monkeypatch)
    descriptor = os.open(launcher.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(OSError):
            tool.install_global_command(launcher, home=home)
        assert not home.exists() and not (launcher.parent / ".chopper-install.json").exists()
    finally:
        os.close(descriptor)
