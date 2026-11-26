import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from chopper.core.cache import AnalysisCache
from chopper.core.settings import Settings
from chopper.gui.main_window import MainWindow


def build_window(settings: Settings | None = None, cache: AnalysisCache | None = None) -> MainWindow:
    return MainWindow(settings=settings, cache=cache)


def default_platform_for_session(env: Mapping[str, str] | None = None) -> str | None:
    """Use native Wayland for Wayland sessions unless a Qt backend was chosen.

    XCB remains an explicit workaround for desktop-specific rendering issues.
    Never hide a missing or broken platform plugin with an automatic fallback.
    """
    env = os.environ if env is None else env
    if env.get("QT_QPA_PLATFORM"):
        return None  # Preserve the user's explicit Qt platform selection.
    if env.get("XDG_SESSION_TYPE") == "wayland":
        return "wayland"
    return None


def default_platform_theme_for_session(env: Mapping[str, str] | None = None) -> str | None:
    """Use KDE's desktop portal so native dialogs expose mounted network locations."""
    env = os.environ if env is None else env
    if env.get("QT_QPA_PLATFORMTHEME"):
        return None
    desktops = env.get("XDG_CURRENT_DESKTOP", "").lower().split(":")
    if "kde" in desktops:
        return "xdgdesktopportal"
    return None


def main(argv: list[str] | None = None) -> None:
    platform = default_platform_for_session()
    if platform:
        os.environ["QT_QPA_PLATFORM"] = platform
    platform_theme = default_platform_theme_for_session()
    if platform_theme:
        os.environ["QT_QPA_PLATFORMTHEME"] = platform_theme

    app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    # Qt consumes its own switches before we interpret the remaining arguments.
    parser = argparse.ArgumentParser(prog="chopper", description="Find, preview and export audio samples.")
    parser.add_argument("path", nargs="?", type=Path, help="Audio file to analyze or album folder to add")
    args = parser.parse_args(app.arguments()[1:])
    initial_path = args.path.expanduser().absolute() if args.path is not None else None
    window = build_window()
    window.show()
    if initial_path is not None:
        QTimer.singleShot(0, lambda: window.open_path(initial_path))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
