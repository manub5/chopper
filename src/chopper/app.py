import argparse
import math
import os
import sys
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from chopper.core.cache import AnalysisCache
from chopper.core.models import LOOP_LENGTHS_BARS
from chopper.core.settings import MAX_SAMPLES_PER_CATEGORY, Settings
from chopper.gui.main_window import MainWindow
from chopper.gui.workers import ChopOptions


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


def _parse_bars(value: str) -> float:
    try:
        bars = Fraction(value)
    except (ValueError, ZeroDivisionError):
        bars = None
    if bars is None or bars not in LOOP_LENGTHS_BARS:
        raise argparse.ArgumentTypeError("choose 1/4, 1/2, 1, 2 or 4 bars")
    return float(bars)


def _parse_arguments(argv: list[str]) -> tuple[Path | None, ChopOptions | None]:
    parser = argparse.ArgumentParser(
        prog="chopper", description="Find, preview and export audio samples.", allow_abbrev=False
    )
    parser.add_argument("path", nargs="?", type=Path, help="Audio file to analyze or album folder to add")
    parser.add_argument("--start", type=float, metavar="SECONDS", help="Start of the chop range (default: 0)")
    parser.add_argument(
        "--end", type=float, metavar="SECONDS", help="End of the chop range (default: track end)"
    )
    parser.add_argument("--bars", type=_parse_bars, help="Loop length: 1/4, 1/2, 1, 2 or 4 bars")
    parser.add_argument(
        "--one-shot-duration", type=float, metavar="SECONDS", help="One-shot duration (0.1-30 s)"
    )
    parser.add_argument("--max-samples", type=int, metavar="N", help="Maximum samples per category (1-64)")
    parser.add_argument("--export-dir", type=Path, help="Write the results to this directory")
    args = parser.parse_args(argv)
    path = args.path.expanduser().absolute() if args.path is not None else None
    values = (args.start, args.end, args.bars, args.one_shot_duration, args.max_samples, args.export_dir)
    if all(value is None for value in values):
        return path, None
    if path is None or not path.is_file():
        parser.error("chop options require an existing audio file")
    start = args.start if args.start is not None else 0.0
    if not math.isfinite(start) or start < 0:
        parser.error("--start must be finite and non-negative")
    if args.end is not None and (not math.isfinite(args.end) or args.end <= start):
        parser.error("--end must be finite and greater than --start")
    if args.one_shot_duration is not None and not 0.1 <= args.one_shot_duration <= 30:
        parser.error("--one-shot-duration must be between 0.1 and 30 seconds")
    if args.max_samples is not None and not 1 <= args.max_samples <= MAX_SAMPLES_PER_CATEGORY:
        parser.error("--max-samples must be between 1 and 64")
    destination = args.export_dir.expanduser().absolute() if args.export_dir is not None else None
    return path, ChopOptions(
        start, args.end, args.bars, args.one_shot_duration, args.max_samples, destination
    )


def main(argv: list[str] | None = None) -> None:
    platform = default_platform_for_session()
    if platform:
        os.environ["QT_QPA_PLATFORM"] = platform
    platform_theme = default_platform_theme_for_session()
    if platform_theme:
        os.environ["QT_QPA_PLATFORMTHEME"] = platform_theme

    app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    # Qt consumes its own switches before we interpret the remaining arguments.
    initial_path, chop = _parse_arguments(app.arguments()[1:])
    window = build_window()
    window.show()
    if initial_path is not None and chop is not None:
        QTimer.singleShot(0, lambda: window.open_file(initial_path, chop=chop))
    elif initial_path is not None:
        QTimer.singleShot(0, lambda: window.open_path(initial_path))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
