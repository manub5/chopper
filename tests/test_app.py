import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from chopper import app as app_module
from chopper.app import build_window, default_platform_for_session, default_platform_theme_for_session
from chopper.core.cache import AnalysisCache
from chopper.core.settings import Settings


def test_build_window_creates_the_main_window(qapp, tmp_path):
    window = build_window(settings=Settings(), cache=AnalysisCache(tmp_path / "cache.sqlite"))
    assert window.windowTitle() == "Chopper"
    window.close()


def test_default_platform_prefers_native_wayland_without_explicit_choice():
    assert default_platform_for_session({"XDG_SESSION_TYPE": "wayland"}) == "wayland"


@pytest.mark.parametrize("platform", ["wayland", "xcb", "offscreen", "custom-plugin"])
def test_default_platform_does_not_override_explicit_choice(platform):
    assert default_platform_for_session({"XDG_SESSION_TYPE": "wayland", "QT_QPA_PLATFORM": platform}) is None


def test_default_platform_leaves_x11_sessions_untouched():
    assert default_platform_for_session({"XDG_SESSION_TYPE": "x11"}) is None
    assert default_platform_for_session({}) is None


def test_default_platform_theme_uses_portal_on_kde():
    assert default_platform_theme_for_session({"XDG_CURRENT_DESKTOP": "KDE"}) == "xdgdesktopportal"


def test_default_platform_theme_does_not_override_explicit_choice():
    env = {"XDG_CURRENT_DESKTOP": "KDE", "QT_QPA_PLATFORMTHEME": "custom"}
    assert default_platform_theme_for_session(env) is None


def test_default_platform_theme_leaves_other_desktops_untouched():
    assert default_platform_theme_for_session({"XDG_CURRENT_DESKTOP": "GNOME"}) is None
    assert default_platform_theme_for_session({}) is None


def test_empty_platform_choice_uses_native_wayland():
    assert default_platform_for_session({"XDG_SESSION_TYPE": "wayland", "QT_QPA_PLATFORM": ""}) == "wayland"


@pytest.mark.parametrize(
    "session, explicit, expected",
    [
        ("wayland", None, "wayland"),
        ("wayland", "xcb", "xcb"),
        ("wayland", "wayland", "wayland"),
        ("wayland", "offscreen", "offscreen"),
        ("x11", None, None),
    ],
)
def test_main_configures_platform_before_qt_and_preserves_kde_portal(
    monkeypatch, session, explicit, expected
):
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.delenv("QT_QPA_PLATFORMTHEME", raising=False)
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    if explicit is not None:
        monkeypatch.setenv("QT_QPA_PLATFORM", explicit)
    consumed = []

    def create_application(args):
        consumed.append((os.environ.get("QT_QPA_PLATFORM"), os.environ.get("QT_QPA_PLATFORMTHEME")))
        return SimpleNamespace(exec=lambda: 0, arguments=lambda: args)

    monkeypatch.setattr(app_module, "QApplication", create_application)
    monkeypatch.setattr(app_module, "build_window", lambda: SimpleNamespace(show=lambda: None))
    monkeypatch.setattr(sys, "argv", ["chopper"])
    with pytest.raises(SystemExit) as stopped:
        app_module.main()
    assert stopped.value.code == 0
    assert consumed == [(expected, "xdgdesktopportal")]


def test_main_without_file_keeps_startup_idle(monkeypatch):
    shown = []
    monkeypatch.setattr(
        app_module, "QApplication", lambda args: SimpleNamespace(arguments=lambda: args, exec=lambda: 0)
    )
    # There is intentionally no file-opening method: idle startup must not call one.
    monkeypatch.setattr(app_module, "build_window", lambda: SimpleNamespace(show=lambda: shown.append(True)))
    with pytest.raises(SystemExit) as stopped:
        app_module.main([])
    assert stopped.value.code == 0 and shown == [True]


@pytest.mark.parametrize("name", ["Track with spaces.wav", "Album with spaces"])
def test_startup_routes_local_target_after_show(monkeypatch, tmp_path, name):
    monkeypatch.chdir(tmp_path)
    path = Path(name)
    if path.suffix:
        path.touch()
    else:
        path.mkdir()
    events = []
    pending = []

    def run():
        pending.pop()()
        return 0

    monkeypatch.setattr(
        app_module, "QApplication", lambda args: SimpleNamespace(arguments=lambda: args, exec=run)
    )
    monkeypatch.setattr(
        app_module, "QTimer", SimpleNamespace(singleShot=lambda delay, fn: pending.append(fn))
    )
    monkeypatch.setattr(
        app_module,
        "build_window",
        lambda: SimpleNamespace(show=lambda: events.append("shown"), open_path=events.append),
    )
    with pytest.raises(SystemExit) as stopped:
        app_module.main([name])
    assert stopped.value.code == 0
    assert events == ["shown", tmp_path / name]


def test_qt_options_are_consumed_before_optional_file_parsing(tmp_path):
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from types import SimpleNamespace
from chopper import app
app.build_window = lambda: SimpleNamespace(show=lambda: None)
original = app.QApplication
def create(args):
    instance = original(args)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, instance.quit)
    return instance
app.QApplication = create
app.main(['-style', 'Fusion'])
""",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "options",
    [
        ["--start", "nan"],
        ["--start", "2", "--end", "1"],
        ["--bars", "3"],
        ["--max-samples", "65"],
        ["--one-shot-duration", "0"],
    ],
)
def test_invalid_chop_options_stop_before_building_window(monkeypatch, tmp_path, options):
    track = tmp_path / "Track.wav"
    track.touch()
    monkeypatch.setattr(app_module, "QApplication", lambda args: SimpleNamespace(arguments=lambda: args))
    monkeypatch.setattr(app_module, "build_window", lambda: pytest.fail("Built a window for invalid options"))
    with pytest.raises(SystemExit) as stopped:
        app_module.main([str(track), *options])
    assert stopped.value.code == 2


def test_chop_options_route_relative_paths_and_reject_album(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    track = tmp_path / "Track with spaces.wav"
    track.touch()
    pending, received = [], []
    monkeypatch.setattr(
        app_module,
        "QApplication",
        lambda args: SimpleNamespace(
            arguments=lambda: args,
            exec=lambda: pending.pop()() or 0,
        ),
    )
    monkeypatch.setattr(
        app_module, "QTimer", SimpleNamespace(singleShot=lambda delay, fn: pending.append(fn))
    )
    monkeypatch.setattr(
        app_module,
        "build_window",
        lambda: SimpleNamespace(
            show=lambda: None,
            open_file=lambda path, *, chop: received.append((path, chop)),
        ),
    )
    with pytest.raises(SystemExit) as stopped:
        app_module.main([track.name, "--start", "0.5", "--bars", "1/2", "--export-dir", "My exports"])
    assert stopped.value.code == 0
    path, chop = received.pop()
    assert path == track and chop.start == 0.5 and chop.bars == 0.5
    assert chop.export_dir == tmp_path / "My exports"
    with pytest.raises(SystemExit) as stopped:
        app_module.main([str(tmp_path), "--bars", "1"])
    assert stopped.value.code == 2 and not received
