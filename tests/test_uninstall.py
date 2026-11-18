import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "integrations_uninstall_test", ROOT / "scripts/install_integrations.py"
    )
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    project = tmp_path / "project with spaces"
    project.mkdir()
    launcher = project / "chopper"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    (project / "assets").mkdir()
    shutil.copyfile(ROOT / "assets/chopper.svg", project / "assets/chopper.svg")
    home = tmp_path / "home"
    data = home / ".local/share"
    desktop = home / "Custom Desktop"
    desktop.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    icon = tool.install_icon(launcher, data_home=data)
    paths = [
        tool._install_menu(launcher, data, icon),
        tool.install_global_command(launcher, home=home),
        icon,
        tool.install_desktop_copy(launcher, desktop_dir=desktop, icon=icon),
    ]
    return tool, project, home, paths


def confirm(monkeypatch, answer="y"):
    monkeypatch.setattr("builtins.input", lambda question: answer)


def test_uninstall_refusal_reinstall_and_repeated_removal_preserve_user_data(installed, monkeypatch):
    tool, project, home, paths = installed
    sentinels = [
        project / "chopper",
        project / ".venv/bin/python",
        project / "exports/sample.wav",
        home / ".profile",
        home / ".bashrc",
        home / ".config/chopper/settings.toml",
        home / ".cache/chopper/analysis.sqlite",
        home / "Music/source.wav",
    ]
    for path in sentinels[1:]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("user sentinel")
    before = {path: path.read_bytes() for path in sentinels}
    receipt = project / tool.RECEIPT_NAME
    original_receipt = receipt.read_bytes()
    confirm(monkeypatch, "n")
    assert tool.uninstall_integrations(project) == 0
    assert receipt.read_bytes() == original_receipt
    assert all(os.path.lexists(path) for path in paths)
    tool.install_icon(project / "chopper", data_home=home / ".local/share")
    assert receipt.read_bytes() == original_receipt
    confirm(monkeypatch)
    parents = {path.parent for path in paths}
    assert tool.uninstall_integrations(project) == 0
    assert all(not os.path.lexists(path) for path in paths) and not receipt.exists()
    assert all(parent.is_dir() for parent in parents)
    assert before == {path: path.read_bytes() for path in sentinels}
    assert tool.uninstall_integrations(project) == 0


@pytest.mark.parametrize("kind", ["modified", "same-bytes", "same-target", "directory", "broken-link"])
def test_uninstall_preserves_modified_or_recreated_artifact(installed, tmp_path, monkeypatch, kind):
    tool, project, _, paths = installed
    path = paths[1] if kind in {"same-target", "broken-link"} else paths[0]
    content = None if path.is_symlink() else path.read_bytes()
    path.rename(tmp_path / "original")
    if kind == "same-target":
        path.symlink_to(project / "chopper")
    elif kind == "broken-link":
        path.symlink_to(tmp_path / "missing")
    elif kind == "directory":
        path.mkdir()
    else:
        path.write_bytes(content if kind == "same-bytes" else b"foreign sentinel")
        path.chmod(0o644)
    before = path.lstat()
    confirm(monkeypatch)
    assert tool.uninstall_integrations(project) != 0
    assert path.lstat().st_ino == before.st_ino
    receipt = tool.load_receipt(project)
    assert len(receipt["artifacts"]) == 1
    assert next(iter(receipt["artifacts"].values()))["path"] == str(path)


def test_changed_desktop_setting_never_targets_new_desktop(installed, tmp_path, monkeypatch):
    tool, project, _, paths = installed
    new_desktop = tmp_path / "New Desktop"
    new_desktop.mkdir()
    foreign = new_desktop / "chopper.desktop"
    foreign.write_bytes(paths[-1].read_bytes())
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "different-config"))
    confirm(monkeypatch)
    assert tool.uninstall_integrations(project) == 0
    assert foreign.exists() and not paths[-1].exists()


@pytest.mark.parametrize("kind", ["corrupt", "other-copy", "symlink"])
def test_invalid_receipt_never_removes_integrations(installed, tmp_path, monkeypatch, kind):
    tool, project, _, paths = installed
    receipt = project / tool.RECEIPT_NAME
    if kind == "other-copy":
        other = tmp_path / "other-copy"
        other.mkdir()
        shutil.copyfile(receipt, other / tool.RECEIPT_NAME)
        project = other
    elif kind == "corrupt":
        receipt.write_text("foreign sentinel")
    else:
        saved = tmp_path / "saved-receipt"
        receipt.rename(saved)
        receipt.symlink_to(saved)
    confirm(monkeypatch)
    assert tool.uninstall_integrations(project) != 0
    assert all(os.path.lexists(path) for path in paths)


def test_missing_artifacts_are_successfully_pruned(installed, monkeypatch):
    tool, project, _, paths = installed
    for path in paths:
        path.unlink()
    confirm(monkeypatch)
    assert tool.uninstall_integrations(project) == 0
    assert not (project / tool.RECEIPT_NAME).exists()


def test_permission_error_keeps_receipt_for_failed_removal(installed, monkeypatch):
    tool, project, _, paths = installed
    failed = paths[0]
    unlink = Path.unlink

    def deny(path, *args, **kwargs):
        if path == failed:
            raise PermissionError("denied sentinel")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny)
    confirm(monkeypatch)
    assert tool.uninstall_integrations(project) != 0
    assert failed.is_file()
    assert set(tool.load_receipt(project)["artifacts"]) == {"menu"}


def test_uninstall_eof_writes_nothing(installed, monkeypatch):
    tool, project, _, paths = installed
    receipt = (project / tool.RECEIPT_NAME).read_bytes()

    def eof(question):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert tool.uninstall_integrations(project) == 0
    assert (project / tool.RECEIPT_NAME).read_bytes() == receipt
    assert all(os.path.lexists(path) for path in paths)


def test_shell_uninstaller_uses_standard_python_without_venv(installed, tmp_path):
    _, project, home, paths = installed
    wrapper = ROOT / "uninstall.sh"
    assert wrapper.is_file()
    shutil.copyfile(wrapper, project / "uninstall.sh")
    (project / "scripts").mkdir()
    for name in ("install_integrations.py", "install_desktop.py"):
        shutil.copyfile(ROOT / "scripts" / name, project / "scripts" / name)
    result = subprocess.run(
        ["bash", str(project / "uninstall.sh")],
        input="y\n",
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        timeout=10,
        env={**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    assert not (project / ".venv").exists()
    assert all(not os.path.lexists(path) for path in paths)


def test_replacement_during_confirmation_is_preserved(installed, tmp_path, monkeypatch):
    tool, project, _, paths = installed
    path = paths[0]
    original = path.read_bytes()

    def replace_at_consent(question):
        path.rename(tmp_path / "old-entry")
        path.write_bytes(original)
        path.chmod(0o644)
        return "y"

    monkeypatch.setattr("builtins.input", replace_at_consent)
    assert tool.uninstall_integrations(project) != 0
    assert path.read_bytes() == original
    assert set(tool.load_receipt(project)["artifacts"]) == {"menu"}


def test_receipt_write_failure_is_reported_and_retry_is_safe(installed, monkeypatch):
    tool, project, _, paths = installed
    # Force one foreign artifact, so the receipt must be updated after other removals.
    paths[0].write_text("modified entry")
    save = tool._save_receipt

    def fail(*args):
        raise PermissionError("receipt write denied")

    monkeypatch.setattr(tool, "_save_receipt", fail)
    confirm(monkeypatch)
    assert tool.uninstall_integrations(project) != 0
    assert (project / tool.RECEIPT_NAME).is_file()
    assert all(not os.path.lexists(path) for path in paths[1:])
    monkeypatch.setattr(tool, "_save_receipt", save)
    assert tool.uninstall_integrations(project) != 0
    assert paths[0].read_text() == "modified entry"
    assert set(tool.load_receipt(project)["artifacts"]) == {"menu"}
