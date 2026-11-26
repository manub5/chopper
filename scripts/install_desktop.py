"""Install a user-owned Desktop Entry after explicit destination consent."""

from __future__ import annotations

import argparse
import configparser
import os
import stat
import sys
import tempfile
from pathlib import Path


def _launcher_exec(launcher: Path) -> str:
    """Quote a launcher using Desktop Entry rules, not shell quoting."""
    path = str(launcher)
    if not launcher.is_absolute():
        raise ValueError("The launcher path must be absolute.")
    if "=" in path or any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError("The launcher path cannot contain '=' or control characters; choose another folder.")
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise ValueError(f"Chopper launcher is missing or not executable: {launcher}")
    # Exec quoting is decoded after the entry's general backslash escaping.
    quoted = "".join("\\" + char if char in '\\"`$' else char for char in path)
    quoted = quoted.replace("%", "%%").replace("\\", "\\\\")
    # GLib checks the executable before expanding %%: keep the path an argument.
    return f'env -- "{quoted}"'


def desktop_entry(launcher: Path, icon: Path | None = None) -> str:
    command = _launcher_exec(launcher)
    icon_value = "audio-x-generic"
    if icon is not None:
        if not icon.is_absolute() or any(ord(char) < 32 or ord(char) == 127 for char in str(icon)):
            raise ValueError("The icon path must be absolute and contain no control characters.")
        icon_value = str(icon).replace("\\", "\\\\")
        if icon_value.startswith(" "):
            icon_value = "\\s" + icon_value[1:]
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Chopper\n"
        "Comment=Find, preview and export loops and one-shots\n"
        f"Exec={command}\n"
        f"Icon={icon_value}\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;\n"
        "X-Chopper-Generated=true\n"
    )


def dolphin_service_entry(launcher: Path) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Service\n"
        "MimeType=inode/directory;audio/vnd.wave;audio/flac;audio/ogg;"
        "audio/x-vorbis+ogg;audio/x-opus+ogg;audio/x-flac+ogg;audio/x-speex+ogg;"
        "audio/x-aiff;audio/mpeg;audio/mp4;audio/aac;\n"
        "X-KDE-Protocols=file\n"
        "X-KDE-RequiredNumberOfUrls=1\n"
        "Actions=openChopper;\n\n"
        "[Desktop Action openChopper]\n"
        "Name=Open with Chopper\n"
        "Name[fr]=Ouvrir avec Chopper\n"
        "Icon=audio-x-generic\n"
        f"Exec={_launcher_exec(launcher)} %f\n"
    )


def _check_destination(destination: Path) -> bool:
    """Return whether an existing regular file is recognizably ours."""
    try:
        mode = destination.lstat().st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(mode):
        raise ValueError(f"Refusing to replace a non-regular file or symlink: {destination}")
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(destination.read_text(encoding="utf-8"))
        own_entry = (
            parser.get("Desktop Entry", "X-Chopper-Generated", fallback="") == "true"
            and parser.get("Desktop Entry", "Type", fallback="") == "Application"
            and parser.get("Desktop Entry", "Name", fallback="") == "Chopper"
        )
    except (configparser.Error, UnicodeError) as error:
        raise ValueError(f"Refusing to overwrite an unrelated shortcut: {destination}") from error
    if not own_entry:
        raise ValueError(f"Refusing to overwrite an unrelated shortcut: {destination}")
    return True


def install_desktop(launcher: Path, data_home: Path) -> Path:
    """Write atomically; the caller must have obtained destination consent."""
    entry = desktop_entry(launcher)
    if not data_home.is_absolute():
        raise ValueError("XDG_DATA_HOME must be an absolute path.")
    destination = data_home / "applications" / "chopper.desktop"
    replacing = _check_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".chopper-",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(entry)
        temporary.chmod(0o644)
        if _check_destination(destination) != replacing:
            raise FileExistsError(f"Shortcut changed during installation; retry: {destination}")
        if replacing:
            os.replace(temporary, destination)
        else:
            # Linking publishes without overwriting a file created concurrently.
            os.link(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", required=True, type=Path)
    args = parser.parse_args()
    try:
        desktop_entry(args.launcher)
        configured = os.environ.get("XDG_DATA_HOME")
        data_home = Path(configured) if configured else Path.home() / ".local" / "share"
        if not data_home.is_absolute():
            raise ValueError("XDG_DATA_HOME must be an absolute path.")
        destination = data_home / "applications" / "chopper.desktop"
        print(f"Optional KDE application menu entry: {destination}")
        print("This may create its parent folders; existing unrelated files will not be overwritten.")
        try:
            answer = input("Create or update the Chopper menu entry there? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in {"y", "yes"}:
            print("Menu entry skipped. You can still start ./chopper from the application folder.")
            return 0
        installed = install_desktop(args.launcher, data_home)
        print(f"Menu entry installed: {installed}")
        return 0
    except (OSError, ValueError) as error:
        print(
            f"Menu entry error: {error}. If local installation succeeded, you can still use ./chopper.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
