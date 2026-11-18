import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HELPER = Path(__file__).parents[1] / "scripts" / "install_desktop.py"


def desktop_tool():
    spec = importlib.util.spec_from_file_location("install_desktop", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def launcher(tmp_path):
    path = tmp_path / "Chopper folder" / "chopper"
    path.parent.mkdir()
    path.write_text('#!/bin/sh\nprintf "launched\\n" > "$CHOPPER_PROBE_OUTPUT"\n')
    path.chmod(0o755)
    return path


def run_helper(launcher, tmp_path, *, answers="", data_home="default"):
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_DATA_HOME": str(tmp_path / "data") if data_home == "default" else data_home,
    }
    if data_home is None:
        env.pop("XDG_DATA_HOME")
    return subprocess.run(
        [sys.executable, str(HELPER), "--launcher", str(launcher)],
        env=env,
        input=answers,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_desktop_entry_identifies_audio_app_and_quotes_launcher(launcher):
    entry = desktop_tool().desktop_entry(launcher)
    assert entry.startswith("[Desktop Entry]\n")
    for field in (
        "Type=Application",
        "Name=Chopper",
        "Terminal=false",
        "Categories=AudioVideo;Audio;",
        "Icon=audio-x-generic",
        "X-Chopper-Generated=true",
    ):
        assert field in entry.splitlines()
    assert f'Exec=env -- "{launcher}"' in entry.splitlines()


def test_icon_path_is_absolute_and_uses_desktop_string_escaping(launcher, tmp_path):
    icon = tmp_path / " icon\\ $cash %f.svg"
    icon.write_text("svg probe")
    entry = desktop_tool().desktop_entry(launcher, icon=icon)
    assert "Icon=" + str(icon).replace("\\", "\\\\") in entry.splitlines()
    with pytest.raises(ValueError):
        desktop_tool().desktop_entry(launcher, icon=Path("relative.svg"))
    with pytest.raises(ValueError):
        desktop_tool().desktop_entry(launcher, icon=tmp_path / "line\nbreak.svg")


@pytest.mark.parametrize("name", ["space ' $cash %f", 'quote"back\\tick`', "échantillon"])
@pytest.mark.parametrize("with_icon", [False, True])
def test_desktop_entry_launches_exact_special_path_with_real_consumer(tmp_path, launcher, name, with_icon):
    gio = shutil.which("gio")
    if gio is None:
        pytest.skip("GLib Desktop Entry launcher unavailable")
    parent = tmp_path / name
    parent.mkdir()
    special_launcher = parent / "chopper"
    shutil.copyfile(launcher, special_launcher)
    special_launcher.chmod(0o755)
    entry = tmp_path / "probe.desktop"
    icon = parent / "chopper.svg" if with_icon else None
    if icon is not None:
        shutil.copyfile(HELPER.parent.parent / "assets/chopper.svg", icon)
    entry.write_text(desktop_tool().desktop_entry(special_launcher, icon))
    output = tmp_path / "probe-output"
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-chopper-test-bus",
        "GIO_USE_VFS": "local",
        "CHOPPER_PROBE_OUTPUT": str(output),
    }
    result = subprocess.run(
        [gio, "launch", str(entry)], env=env, capture_output=True, text=True, check=False, timeout=10
    )
    assert result.returncode == 0, result.stderr
    deadline = time.monotonic() + 3
    while not output.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert output.read_text() == "launched\n"


@pytest.mark.parametrize("with_icon", [False, True])
def test_desktop_entry_passes_official_validator(tmp_path, launcher, with_icon):
    validator = shutil.which("desktop-file-validate")
    if validator is None:
        pytest.skip("Desktop Entry validator unavailable")
    entry = tmp_path / "chopper.desktop"
    icon = tmp_path / "icon \\ $cash %f.svg" if with_icon else None
    if icon is not None:
        shutil.copyfile(HELPER.parent.parent / "assets/chopper.svg", icon)
    entry.write_text(desktop_tool().desktop_entry(launcher, icon))
    result = subprocess.run([validator, str(entry)], capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("name", ["line\nbreak", "carriage\rreturn", "equal=sign", "tab\tpath"])
def test_unsafe_exec_paths_are_rejected_without_writes(tmp_path, name):
    parent = tmp_path / name
    parent.mkdir()
    path = parent / "chopper"
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    with pytest.raises(ValueError):
        desktop_tool().install_desktop(path, tmp_path / "data")
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("answers", ["n\n", "\n", ""])
def test_shortcut_decline_or_eof_writes_nothing(tmp_path, launcher, answers):
    result = run_helper(launcher, tmp_path, answers=answers)
    assert result.returncode == 0, result.stderr
    assert str(tmp_path / "data/applications/chopper.desktop") in result.stdout
    assert "skipped" in result.stdout.lower()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("custom_xdg", [True, False])
def test_shortcut_written_only_after_confirming_displayed_destination(tmp_path, launcher, custom_xdg):
    result = run_helper(launcher, tmp_path, answers="y\n", data_home="default" if custom_xdg else None)
    destination = (
        tmp_path / "data" if custom_xdg else tmp_path / "home/.local/share"
    ) / "applications/chopper.desktop"
    assert result.returncode == 0, result.stderr
    assert str(destination) in result.stdout
    assert f'Exec=env -- "{launcher}"' in destination.read_text().splitlines()


def test_relative_xdg_destination_is_rejected(tmp_path, launcher):
    result = run_helper(launcher, tmp_path, answers="y\n", data_home="relative-chopper-test-location")
    assert result.returncode != 0
    assert "absolute" in result.stderr.lower()
    assert not (tmp_path / "home").exists()


def test_reinstallation_updates_only_own_entry(tmp_path, launcher):
    tool = desktop_tool()
    destination = tool.install_desktop(launcher, tmp_path / "data")
    first = destination.read_bytes()
    assert tool.install_desktop(launcher, tmp_path / "data") == destination
    assert destination.read_bytes() == first
    replacement = launcher.with_name("chopper-new")
    shutil.copyfile(launcher, replacement)
    replacement.chmod(0o755)
    tool.install_desktop(replacement, tmp_path / "data")
    assert f'Exec=env -- "{replacement}"' in destination.read_text().splitlines()
    assert list(destination.parent.iterdir()) == [destination]


@pytest.mark.parametrize(
    "content",
    [
        "foreign file sentinel",
        "[Desktop Entry]\nType=Application\nName=Other\nX-Chopper-Generated=true\n",
        "[Desktop Entry]\nType=Link\nName=Chopper\nX-Chopper-Generated=true\n",
        "[Desktop Entry]\nType=Application\nName=Chopper\n",
    ],
)
def test_foreign_shortcut_is_preserved(tmp_path, launcher, content):
    tool = desktop_tool()
    destination = tmp_path / "data/applications/chopper.desktop"
    destination.parent.mkdir(parents=True)
    destination.write_text(content)
    with pytest.raises((OSError, ValueError)):
        tool.install_desktop(launcher, tmp_path / "data")
    assert destination.read_text() == content
    assert list(destination.parent.iterdir()) == [destination]


@pytest.mark.parametrize("broken", [False, True])
def test_shortcut_symlink_is_never_replaced_or_followed(tmp_path, launcher, broken):
    tool = desktop_tool()
    destination = tmp_path / "data/applications/chopper.desktop"
    destination.parent.mkdir(parents=True)
    target = tmp_path / "target.desktop"
    if not broken:
        target.write_text(tool.desktop_entry(launcher))
    destination.symlink_to(target)
    with pytest.raises((OSError, ValueError)):
        tool.install_desktop(launcher, tmp_path / "data")
    assert destination.is_symlink()
    assert target.exists() is not broken
    if not broken:
        assert target.read_text() == tool.desktop_entry(launcher)


def test_failed_atomic_replace_preserves_old_entry_and_cleans_temp(tmp_path, launcher, monkeypatch):
    tool = desktop_tool()
    destination = tool.install_desktop(launcher, tmp_path / "data")
    previous = destination.read_bytes()

    def fail_replace(*args):
        raise PermissionError("simulated directory write failure")

    monkeypatch.setattr(tool.os, "replace", fail_replace)
    with pytest.raises(PermissionError):
        tool.install_desktop(launcher, tmp_path / "data")
    assert destination.read_bytes() == previous
    assert list(destination.parent.iterdir()) == [destination]


def test_cli_reports_write_error_without_changing_launcher(tmp_path, launcher):
    (tmp_path / "data").write_text("blocked directory sentinel")
    previous = launcher.read_bytes()
    result = run_helper(launcher, tmp_path, answers="y\n")
    assert result.returncode != 0
    assert "error" in result.stderr.lower()
    assert "installed" not in result.stdout.lower()
    assert (tmp_path / "data").read_text() == "blocked directory sentinel"
    assert launcher.read_bytes() == previous


def test_missing_launcher_is_rejected_without_creating_destination(tmp_path):
    result = run_helper(tmp_path / "missing-chopper", tmp_path, answers="y\n")
    assert result.returncode != 0
    assert not (tmp_path / "data").exists()
