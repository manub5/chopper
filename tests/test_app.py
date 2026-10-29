from choppeur.app import build_window, default_platform_for_session, default_platform_theme_for_session
from choppeur.core.cache import AnalysisCache
from choppeur.core.settings import Settings


def test_build_window_creates_the_main_window(qapp, tmp_path):
    window = build_window(settings=Settings(), cache=AnalysisCache(tmp_path / "cache.sqlite"))
    assert window.windowTitle() == "Choppeur"
    window.close()


def test_default_platform_prefers_xcb_on_wayland_without_explicit_choice():
    assert default_platform_for_session({"XDG_SESSION_TYPE": "wayland"}) == "xcb"


def test_default_platform_does_not_override_explicit_choice():
    assert default_platform_for_session({"XDG_SESSION_TYPE": "wayland", "QT_QPA_PLATFORM": "wayland"}) is None


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
