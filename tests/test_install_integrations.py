import importlib.util
import json
import os
import shutil
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
        env={
            **os.environ,
            "HOME": str(home),
            "XDG_DATA_HOME": str(data),
            "XDG_CONFIG_HOME": str(home / "config"),
            "PATH": path or initial_path,
        },
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


def test_dolphin_action_is_opt_in_and_tracked(installation, monkeypatch):
    launcher, _, data = installation
    destination = data / "kio/servicemenus/chopper-open.desktop"
    assert cli(installation, answers="n\nn\nn\n").returncode == 0
    assert not destination.exists()
    result = cli(installation, answers="n\nn\nn\ny\n")
    assert result.returncode == 0, result.stderr
    original = destination.read_bytes()
    assert b"Type=Service\n" in original and b" %f\n" in original
    assert destination.stat().st_mode & 0o777 == 0o755
    tool = integration_tool(monkeypatch)
    assert tool.load_receipt(launcher.parent)["artifacts"]["dolphin-service"]["path"] == str(destination)
    inode = destination.stat().st_ino
    assert cli(installation, answers="n\nn\nn\ny\n").returncode == 0
    assert destination.stat().st_ino == inode
    monkeypatch.setattr("builtins.input", lambda *args: "y")
    assert tool.uninstall_integrations(launcher.parent) == 0
    assert not destination.exists()


def test_dolphin_action_never_replaces_foreign_file(installation):
    _, _, data = installation
    destination = data / "kio/servicemenus/chopper-open.desktop"
    destination.parent.mkdir(parents=True)
    destination.write_text("foreign entry")
    destination.chmod(0o755)
    assert cli(installation, answers="n\nn\nn\ny\n").returncode != 0
    assert destination.read_text() == "foreign entry"


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
    # The historical Exec field escapes both dollar signs and field-code markers.
    quoted = str(launcher).replace("$", r"\\$").replace("%", "%%")
    entry = data / "applications/chopper.desktop"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "[Desktop Entry]\nType=Application\nName=Chopper\n"
        "Comment=Find, preview and export loops and one-shots\n"
        f'Exec=env -- "{quoted}"\n'
        "Icon=audio-x-generic\nTerminal=false\nCategories=AudioVideo;Audio;\nX-Chopper-Generated=true\n"
    )
    entry.chmod(0o644)
    status = entry.stat()
    os.utime(entry, ns=(1, status.st_mtime_ns))
    result = cli(installation, answers="y\nn\n")
    assert result.returncode == 0, result.stderr
    assert f'Exec=env -- "{quoted}"' in entry.read_text().splitlines()
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


def copy_icon_source(launcher):
    source = SCRIPTS.parent / "assets/chopper.svg"
    assert source.is_file(), "The dedicated SVG must be shipped"
    destination = launcher.parent / "assets/chopper.svg"
    destination.parent.mkdir(exist_ok=True)
    shutil.copyfile(source, destination)


def xdg_tool(tmp_path, output, *, status=0):
    tools = tmp_path / "xdg tools"
    tools.mkdir(exist_ok=True)
    script = tools / "xdg-user-dir"
    script.write_text(
        f"#!/bin/sh\n[ \"$1\" = DESKTOP ] || exit 98\nprintf '%s\\n' '{output}'\nexit {status}\n"
    )
    script.chmod(0o755)
    return str(tools)


def test_svg_is_static_and_renders_at_small_sizes():
    import xml.etree.ElementTree as ET

    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    source = SCRIPTS.parent / "assets/chopper.svg"
    assert source.is_file()
    root = ET.fromstring(source.read_bytes())
    assert root.attrib["viewBox"] == "0 0 64 64"
    for element in root.iter():
        assert element.tag.split("}")[-1] in {"svg", "rect", "path", "circle", "g", "title"}
        assert all(not key.lower().startswith("on") and "href" not in key for key in element.attrib)
        assert all("url(" not in value for value in element.attrib.values())
    assert {"#4285F4", "#EA4335", "#FBBC04", "#34A853"} <= {
        value for node in root.iter() for value in node.attrib.values()
    }
    renderer = QSvgRenderer(str(source))
    assert renderer.isValid()
    for size in (16, 32, 64):
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        assert image.pixelColor(size // 2, size // 2).alpha() > 0
        assert any(image.pixelColor(x, y).red() > 150 for x in range(size) for y in range(size))


def test_all_integrations_share_icon_and_desktop_content(installation, tmp_path):
    launcher, home, data = installation
    copy_icon_source(launcher)
    desktop = tmp_path / "My desktop with spaces"
    desktop.mkdir()
    path = xdg_tool(tmp_path, desktop)
    result = cli(installation, answers="y\ny\ny\ny\n", path=path)
    assert result.returncode == 0, result.stderr
    icon = data / "icons/hicolor/scalable/apps/chopper.svg"
    menu = data / "applications/chopper.desktop"
    shortcut = desktop / "chopper.desktop"
    assert icon.read_bytes() == (launcher.parent / "assets/chopper.svg").read_bytes()
    assert shortcut.read_bytes() == menu.read_bytes()
    assert f"Icon={icon}" in menu.read_text().splitlines()
    assert shortcut.stat().st_mode & 0o777 == 0o755
    receipt = launcher.parent / ".chopper-install.json"
    before = receipt.read_bytes()
    stamps = [p.stat().st_ino for p in (icon, menu, shortcut)]
    again = cli(installation, answers="y\ny\ny\ny\n", path=path)
    assert again.returncode == 0, again.stderr
    assert receipt.read_bytes() == before
    assert stamps == [p.stat().st_ino for p in (icon, menu, shortcut)]
    assert set(json.loads(before)["artifacts"]) == {"menu", "global-command", "icon", "desktop"}
    assert not (home / "Desktop").exists()


@pytest.mark.parametrize("output,status", [("", 0), ("relative", 0), ("HOME", 0), ("unused", 1)])
def test_invalid_xdg_desktop_never_creates_a_fallback(installation, tmp_path, output, status):
    _, home, data = installation
    path = xdg_tool(tmp_path, home if output == "HOME" else output, status=status)
    result = cli(installation, answers="n\nn\nn\nn\n", path=path)
    assert result.returncode == 0, result.stderr
    assert "Desktop shortcut unavailable" in result.stdout
    assert not home.exists() and not data.exists()


def test_missing_xdg_tool_is_reported_without_writes(installation, tmp_path):
    tools = tmp_path / "empty-tools"
    tools.mkdir()
    result = cli(installation, answers="n\nn\nn\ny\n", path=str(tools))
    assert result.returncode == 0, result.stderr
    assert "Desktop shortcut unavailable" in result.stdout


@pytest.mark.parametrize("role", ["icon", "desktop", "menu"])
@pytest.mark.parametrize("kind", ["foreign", "symlink", "directory", "identical-unowned"])
def test_new_integrations_refuse_unowned_destinations(installation, tmp_path, monkeypatch, role, kind):
    launcher, _, data = installation
    tool = integration_tool(monkeypatch)
    copy_icon_source(launcher)
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    if role == "icon":
        destination = data / "icons/hicolor/scalable/apps/chopper.svg"
        content = (launcher.parent / "assets/chopper.svg").read_bytes()

        def action():
            return tool.install_icon(launcher, data_home=data)
    else:
        destination = (desktop if role == "desktop" else data / "applications") / "chopper.desktop"
        content = tool.desktop_entry(launcher, icon=None).encode()
        action = (
            (lambda: tool.install_desktop_copy(launcher, desktop_dir=desktop, icon=None))
            if role == "desktop"
            else (lambda: tool._install_menu(launcher, data))
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if kind == "directory":
        destination.mkdir()
    elif kind == "symlink":
        destination.symlink_to(tmp_path / "missing")
    else:
        destination.write_bytes(content if kind == "identical-unowned" else b"foreign sentinel")
        destination.chmod(0o755 if role == "desktop" else 0o644)
    before = destination.lstat()
    if role == "menu" and kind == "identical-unowned":
        action()  # Only the exact historical menu is adoptable.
    else:
        with pytest.raises((OSError, ValueError)):
            action()
    assert destination.lstat().st_ino == before.st_ino


def test_menu_can_switch_owned_icon_and_preserves_old_bytes_on_receipt_failure(installation, monkeypatch):
    launcher, _, data = installation
    tool = integration_tool(monkeypatch)
    copy_icon_source(launcher)
    entry = tool._install_menu(launcher, data)
    old = entry.read_bytes()
    icon = tool.install_icon(launcher, data_home=data)
    original_save = tool._save_receipt

    def fail(*args):
        raise PermissionError("receipt unavailable")

    monkeypatch.setattr(tool, "_save_receipt", fail)
    with pytest.raises(OSError):
        tool._install_menu(launcher, data, icon=icon)
    assert entry.read_bytes() == old
    monkeypatch.setattr(tool, "_save_receipt", original_save)
    tool._install_menu(launcher, data, icon=icon)
    assert f"Icon={icon}" in entry.read_text().splitlines()
    assert tool.load_receipt(launcher.parent)["artifacts"]["menu"] == tool._stamp(entry)


def test_declined_icon_keeps_shortcuts_generic(installation, tmp_path):
    _, _, data = installation
    desktop = tmp_path / "Desktop space"
    desktop.mkdir()
    path = xdg_tool(tmp_path, desktop)
    result = cli(installation, answers="y\nn\nn\ny\n", path=path)
    assert result.returncode == 0, result.stderr
    assert (desktop / "chopper.desktop").read_bytes() == (data / "applications/chopper.desktop").read_bytes()
    assert "Icon=audio-x-generic" in (desktop / "chopper.desktop").read_text()
    assert not (data / "icons").exists()


@pytest.mark.parametrize("role", ["icon", "desktop"])
def test_owned_file_modified_or_recreated_is_preserved(installation, tmp_path, monkeypatch, role):
    launcher, _, data = installation
    copy_icon_source(launcher)
    tool = integration_tool(monkeypatch)
    desktop = tmp_path / "desktop"
    desktop.mkdir()

    def install():
        return (
            tool.install_icon(launcher, data_home=data)
            if role == "icon"
            else tool.install_desktop_copy(launcher, desktop_dir=desktop, icon=None)
        )

    path = install()
    original = path.read_bytes()
    path.rename(tmp_path / "old-file")
    path.write_bytes(original)
    path.chmod(0o644 if role == "icon" else 0o755)
    before = path.stat()
    with pytest.raises((OSError, ValueError)):
        install()
    assert path.read_bytes() == original and path.stat().st_ino == before.st_ino


@pytest.mark.parametrize("role", ["icon", "desktop"])
def test_new_file_receipt_failure_rolls_back_created_object(installation, tmp_path, monkeypatch, role):
    launcher, _, data = installation
    copy_icon_source(launcher)
    tool = integration_tool(monkeypatch)
    desktop = tmp_path / "desktop"
    desktop.mkdir()

    def fail(*args):
        raise PermissionError("receipt full")

    monkeypatch.setattr(tool, "_save_receipt", fail)
    with pytest.raises(OSError):
        if role == "icon":
            tool.install_icon(launcher, data_home=data)
        else:
            tool.install_desktop_copy(launcher, desktop_dir=desktop, icon=None)
    assert not (desktop / "chopper.desktop").exists()
    assert not (data / "icons/hicolor/scalable/apps/chopper.svg").exists()


def test_failed_receipt_update_restores_without_allocating_another_file(installation, monkeypatch):
    launcher, _, data = installation
    tool = integration_tool(monkeypatch)
    copy_icon_source(launcher)
    entry = tool._install_menu(launcher, data)
    old = entry.read_bytes()
    icon = tool.install_icon(launcher, data_home=data)
    publish = tool._publish_bytes
    receipt_failed = False

    def fail_receipt(*args):
        nonlocal receipt_failed
        receipt_failed = True
        raise OSError("disk full")

    def no_further_allocation(path, content, mode, expected):
        if receipt_failed:
            raise OSError("disk still full")
        return publish(path, content, mode, expected)

    monkeypatch.setattr(tool, "_save_receipt", fail_receipt)
    monkeypatch.setattr(tool, "_publish_bytes", no_further_allocation)
    with pytest.raises(OSError):
        tool._install_menu(launcher, data, icon=icon)
    assert entry.read_bytes() == old


def test_public_replacement_at_destructive_operation_is_preserved(installation, tmp_path, monkeypatch):
    launcher, _, data = installation
    tool = integration_tool(monkeypatch)
    copy_icon_source(launcher)
    entry = tool._install_menu(launcher, data)
    icon = tool.install_icon(launcher, data_home=data)
    replace = tool.os.replace
    rename = tool.os.rename
    injected = False

    def inject():
        nonlocal injected
        if not injected:
            injected = True
            rename(entry, tmp_path / "saved-menu")
            entry.write_text("foreign last-moment sentinel")

    def race_replace(source, destination, *args, **kwargs):
        if Path(destination) == entry:
            inject()
        return replace(source, destination, *args, **kwargs)

    def race_rename(source, destination, *args, **kwargs):
        if Path(source) == entry:
            inject()
        return rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(tool.os, "replace", race_replace)
    monkeypatch.setattr(tool.os, "rename", race_rename)
    if hasattr(tool, "_rename_no_replace"):
        no_replace = tool._rename_no_replace

        def race_capture(source, destination):
            if source == entry:
                inject()
            return no_replace(source, destination)

        monkeypatch.setattr(tool, "_rename_no_replace", race_capture)
    with pytest.raises((OSError, ValueError)):
        tool._install_menu(launcher, data, icon=icon)
    assert injected and entry.read_text() == "foreign last-moment sentinel"


def test_whole_installation_blocks_interleaved_uninstall(installation, tmp_path, monkeypatch):
    launcher, home, data = installation
    copy_icon_source(launcher)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    tool = integration_tool(monkeypatch)
    monkeypatch.setattr(tool, "_confirm", lambda *args: True)
    monkeypatch.setattr(tool, "_desktop_directory", lambda *args: desktop)
    attempts = []
    report = tool._report_path

    def uninstall_after_command(*args):
        report(*args)
        result = subprocess.run(
            [sys.executable, str(HELPER), "--uninstall", "--project", str(launcher.parent)],
            input="y\n",
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        attempts.append(result)

    monkeypatch.setattr(tool, "_report_path", uninstall_after_command)
    assert tool.install_integrations(launcher, initial_path="/usr/bin:/bin") == 0
    assert len(attempts) == 1 and attempts[0].returncode != 0
    receipt = tool.load_receipt(launcher.parent)
    assert set(receipt["artifacts"]) == {"menu", "icon", "global-command", "desktop", "dolphin-service"}
    assert all(tool._stamp(Path(record["path"])) == record for record in receipt["artifacts"].values())


def test_rollback_conflict_preserves_foreign_file_and_original_backup(installation, tmp_path, monkeypatch):
    launcher, _, data = installation
    tool = integration_tool(monkeypatch)
    copy_icon_source(launcher)
    entry = tool._install_menu(launcher, data)
    old = entry.read_bytes()
    icon = tool.install_icon(launcher, data_home=data)
    failed = False
    capture = tool._rename_no_replace

    def fail_receipt(*args):
        nonlocal failed
        failed = True
        raise PermissionError("receipt unavailable")

    def race_capture(source, destination):
        if failed and source == entry:
            # Replace precisely at the rollback capture boundary.
            os.rename(entry, tmp_path / "new-chopper-entry")
            entry.write_text("foreign rollback sentinel")
        return capture(source, destination)

    monkeypatch.setattr(tool, "_save_receipt", fail_receipt)
    monkeypatch.setattr(tool, "_rename_no_replace", race_capture)
    with pytest.raises((OSError, ValueError)):
        tool._install_menu(launcher, data, icon=icon)
    assert entry.read_text() == "foreign rollback sentinel"
    backups = list(entry.parent.glob(".chopper-rollback-*/original"))
    assert any(path.read_bytes() == old for path in backups)
