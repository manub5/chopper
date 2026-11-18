"""Install optional user integrations with consent and a local ownership receipt."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from install_desktop import desktop_entry

RECEIPT_NAME = ".chopper-install.json"


@contextmanager
def _project_lock(project: Path) -> Iterator[None]:
    # Linux directory locks serialize our helpers without creating a lock file.
    descriptor = os.open(project, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BlockingIOError(f"Another installation is updating this project: {project}") from error
        yield
    finally:
        os.close(descriptor)


def _stat_identity(status: os.stat_result) -> tuple[int, ...]:
    # Reading may update atime; that is not a replacement or content edit.
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_ctime_ns,
        status.st_mtime_ns,
        status.st_size,
    )


def _absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError(f"Expected an absolute path: {path}")
    return path


def _stamp(path: Path) -> dict | None:
    """Identify the object itself and its parent, never follow a final symlink."""
    try:
        status = path.lstat()
    except FileNotFoundError:
        return None
    result = {
        "path": str(path),
        "parent": str(path.parent.resolve(strict=True)),
        "device": status.st_dev,
        "inode": status.st_ino,
        "ctime_ns": status.st_ctime_ns,
        "mode": stat.S_IMODE(status.st_mode),
    }
    if stat.S_ISLNK(status.st_mode):
        result.update(type="symlink", target=os.readlink(path))
    elif stat.S_ISREG(status.st_mode):
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if _stat_identity(opened) != _stat_identity(status):
                raise FileExistsError(f"File changed while checking: {path}")
            result.update(type="file", sha256=hashlib.sha256(stream.read()).hexdigest())
    else:
        raise ValueError(f"Refusing a non-regular file: {path}")
    if _stat_identity(path.lstat()) != _stat_identity(status):
        raise FileExistsError(f"File changed while checking: {path}")
    return result


def _validate_receipt(data: object, project: Path) -> dict:
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "project", "artifacts"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["project"] != str(project)
        or not isinstance(data["artifacts"], dict)
    ):
        raise ValueError("Foreign or invalid Chopper installation receipt.")
    for role, record in data["artifacts"].items():
        if role not in {"global-command", "menu", "icon", "desktop"} or not isinstance(record, dict):
            raise ValueError("Invalid receipt artifact role.")
        is_link = role == "global-command"
        expected = {
            "path",
            "parent",
            "device",
            "inode",
            "ctime_ns",
            "mode",
            "type",
            "target" if is_link else "sha256",
        }
        if set(record) != expected:
            raise ValueError("Invalid receipt artifact fields.")
        if any(
            type(record[key]) is not int or record[key] < 0 for key in ("device", "inode", "ctime_ns", "mode")
        ):
            raise ValueError("Invalid receipt file identity.")
        if record["mode"] > 0o7777 or record["type"] != ("symlink" if is_link else "file"):
            raise ValueError("Invalid receipt artifact type or permissions.")
        for key in ("path", "parent"):
            if not isinstance(record[key], str) or "\0" in record[key] or not Path(record[key]).is_absolute():
                raise ValueError("Invalid receipt artifact path.")
        destination = Path(record["path"])
        if is_link:
            if (
                destination.name != "chopper"
                or destination.parent.name != "bin"
                or destination.parent.parent.name != ".local"
                or record["target"] != str(project / "chopper")
            ):
                raise ValueError("Invalid receipt command destination or target.")
        elif (
            (
                role == "menu"
                and (destination.name != "chopper.desktop" or destination.parent.name != "applications")
            )
            or (role == "desktop" and destination.name != "chopper.desktop")
            or (
                role == "icon"
                and tuple(destination.parts[-5:]) != ("icons", "hicolor", "scalable", "apps", "chopper.svg")
            )
            or not isinstance(record["sha256"], str)
            or len(record["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in record["sha256"])
        ):
            raise ValueError("Invalid receipt menu destination or digest.")
    return data


def _read_receipt(project: Path) -> tuple[dict, dict | None]:
    path = project / RECEIPT_NAME
    try:
        status = path.lstat()
    except FileNotFoundError:
        return {"schema_version": 1, "project": str(project), "artifacts": {}}, None
    if not stat.S_ISREG(status.st_mode) or status.st_size > 65536:
        raise ValueError(f"Refusing a foreign receipt or symlink: {path}")
    before = _stamp(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if _stamp(path) != before:
        raise FileExistsError(f"Receipt changed while reading: {path}")
    return _validate_receipt(data, project), before


def load_receipt(project: Path) -> dict:
    return _read_receipt(_absolute(project).resolve(strict=True))[0]


def _publish_bytes(path: Path, content: bytes, mode: int, expected: dict | None) -> dict:
    """Publish new files exclusively; only replace an unchanged owned object."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".chopper-", suffix=".tmp", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            temporary.chmod(mode)
            if _stamp(path) != expected:
                raise FileExistsError(f"Destination changed during installation: {path}")
            if expected is None:
                os.link(temporary, path)
            else:
                os.replace(temporary, path)
            temporary.unlink(missing_ok=True)
            created = _stamp(path)
            owned = os.fstat(stream.fileno())
            if (
                created is None
                or created["type"] != "file"
                or created["device"] != owned.st_dev
                or created["inode"] != owned.st_ino
                or created["ctime_ns"] != owned.st_ctime_ns
                or created["mode"] != mode
                or created["sha256"] != hashlib.sha256(content).hexdigest()
            ):
                raise FileExistsError(f"File changed during publication; preserving it: {path}")
            return created
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _save_receipt(project: Path, data: dict, expected: dict | None) -> None:
    _validate_receipt(data, project)
    content = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _publish_bytes(project / RECEIPT_NAME, content, 0o600, expected)


def _rollback_created(path: Path, created: dict) -> None:
    if _stamp(path) == created:
        path.unlink()


def install_global_command(launcher: Path, *, home: Path) -> Path:
    """Create the command after consent; an identical but unowned link is foreign."""
    launcher = _absolute(launcher).resolve(strict=True)
    desktop_entry(launcher)  # Keep launcher validation consistent with the menu.
    with _project_lock(launcher.parent):
        return _install_global_command(launcher, home=home)


def _install_global_command(launcher: Path, *, home: Path) -> Path:
    project = launcher.parent
    data, receipt_before = _read_receipt(project)
    destination = _absolute(home).resolve() / ".local" / "bin" / "chopper"
    previous = data["artifacts"].get("global-command")
    if os.path.lexists(destination):
        if previous is None or previous["path"] != str(destination) or _stamp(destination) != previous:
            raise ValueError(f"Refusing to overwrite an unowned or modified command: {destination}")
        return destination
    if previous is not None and previous["path"] != str(destination):
        raise ValueError(
            "Receipt belongs to a different command destination; uninstall that integration first."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    try:
        with tempfile.TemporaryDirectory(prefix=".chopper-link-", dir=destination.parent) as temporary:
            staged = Path(temporary) / "command"
            staged.symlink_to(launcher)
            # Linux O_PATH keeps our symlink inode alive, even after a concurrent replacement.
            descriptor = os.open(staged, os.O_PATH | os.O_NOFOLLOW)
            os.link(staged, destination, follow_symlinks=False)
        owned = os.fstat(descriptor)
        created = _stamp(destination)
        if (
            created is None
            or created["type"] != "symlink"
            or created["target"] != str(launcher)
            or created["device"] != owned.st_dev
            or created["inode"] != owned.st_ino
            or created["ctime_ns"] != owned.st_ctime_ns
        ):
            raise FileExistsError(f"Command changed during publication; preserving it: {destination}")
        data["artifacts"]["global-command"] = created
        try:
            _save_receipt(project, data, receipt_before)
        except (OSError, ValueError):
            _rollback_created(destination, created)
            raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return destination


def _install_menu(launcher: Path, data_home: Path, icon: Path | None = None) -> Path:
    launcher = _absolute(launcher).resolve(strict=True)
    with _project_lock(launcher.parent):
        return _install_file(
            launcher,
            "menu",
            _absolute(data_home) / "applications/chopper.desktop",
            desktop_entry(launcher, icon).encode(),
            0o644,
            legacy=desktop_entry(launcher).encode(),
        )


def _install_file(
    launcher: Path, role: str, destination: Path, content: bytes, mode: int, *, legacy: bytes | None = None
) -> Path:
    project = launcher.parent
    data, receipt_before = _read_receipt(project)
    previous = data["artifacts"].get(role)
    current = _stamp(destination)
    if previous is not None and (
        previous["path"] != str(destination) or (current is not None and previous != current)
    ):
        raise ValueError(f"Refusing to overwrite an unowned or modified {role}: {destination}")
    old_content = None
    if current is not None:
        if current["type"] != "file" or current["mode"] != mode:
            raise ValueError(f"Refusing to overwrite an unrelated {role}: {destination}")
        old_content = destination.read_bytes()
        if previous is None and (legacy is None or old_content != legacy):
            raise ValueError(f"Refusing to overwrite an unrelated {role}: {destination}")
        if previous is not None and old_content == content:
            return destination
    before = current
    with _restore_point(destination, old_content if old_content != content else None, mode) as backup:
        if old_content != content:
            current = _publish_bytes(destination, content, mode, current)
        assert current is not None
        data["artifacts"][role] = current
        try:
            _save_receipt(project, data, receipt_before)
        except (OSError, ValueError):
            if before is None:
                _rollback_created(destination, current)
            elif backup is not None and _stamp(destination) == current:
                # The backup was allocated before mutation, so even disk-full rollback can rename it.
                saved, descriptor = backup
                saved_stamp = _stamp(saved)
                owned = os.fstat(descriptor)
                if saved_stamp is None or (saved_stamp["device"], saved_stamp["inode"]) != (
                    owned.st_dev,
                    owned.st_ino,
                ):
                    raise FileExistsError("Rollback backup changed; refusing to use it.") from None
                os.replace(saved, destination)
                restored = _stamp(destination)
                if restored is None or (restored["device"], restored["inode"]) != (
                    owned.st_dev,
                    owned.st_ino,
                ):
                    raise FileExistsError("Restored entry changed concurrently; preserving it.") from None
                if previous is None:
                    data["artifacts"].pop(role)
                else:
                    data["artifacts"][role] = restored
                if receipt_before is not None:
                    recovery = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
                    try:
                        _publish_bytes(project / RECEIPT_NAME, recovery, 0o600, receipt_before)
                    except (OSError, ValueError) as recovery_error:
                        raise OSError(
                            "Old integration content restored, but its receipt could not be refreshed; "
                            "further changes will be refused safely."
                        ) from recovery_error
            raise
    return destination


@contextmanager
def _restore_point(path: Path, content: bytes | None, mode: int) -> Iterator[tuple[Path, int] | None]:
    if content is None:
        yield None
        return
    with tempfile.TemporaryDirectory(prefix=".chopper-rollback-", dir=path.parent) as directory:
        saved = Path(directory) / "original"
        with saved.open("xb") as stream:
            stream.write(content)
            stream.flush()
            saved.chmod(mode)
            yield saved, stream.fileno()


def install_icon(launcher: Path, *, data_home: Path) -> Path:
    launcher = _absolute(launcher).resolve(strict=True)
    desktop_entry(launcher)
    content = (launcher.parent / "assets/chopper.svg").read_bytes()
    with _project_lock(launcher.parent):
        return _install_file(
            launcher, "icon", _absolute(data_home) / "icons/hicolor/scalable/apps/chopper.svg", content, 0o644
        )


def install_desktop_copy(launcher: Path, *, desktop_dir: Path, icon: Path | None) -> Path:
    launcher = _absolute(launcher).resolve(strict=True)
    desktop_dir = _absolute(desktop_dir)
    if not desktop_dir.is_dir() or desktop_dir.resolve() == Path.home().resolve():
        raise ValueError("Desktop directory must exist and differ from HOME.")
    with _project_lock(launcher.parent):
        return _install_file(
            launcher,
            "desktop",
            desktop_dir / "chopper.desktop",
            desktop_entry(launcher, icon).encode(),
            0o755,
        )


def _desktop_directory(home: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, check=True, timeout=5
        )
        value = result.stdout.rstrip("\n")
        path = Path(value)
        if not value or not path.is_absolute() or not path.is_dir() or path.resolve() == home:
            raise ValueError("XDG DESKTOP is empty, relative, missing, or disabled (HOME).")
        return path.resolve()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Desktop shortcut unavailable: {error}. No fallback folder will be created.")
        return None


def _confirm(destination: Path, project: Path, question: str) -> bool:
    print(f"Optional destination: {destination}")
    print(f"Local ownership receipt: {project / RECEIPT_NAME}")
    print("Parent folders may be created after consent. Unrelated or modified files will not be replaced.")
    try:
        answer = input(f"{question} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def _report_path(home: Path, initial_path: str, destination: Path) -> None:
    bin_directory = home / ".local" / "bin"
    if not any(
        part and Path(part).is_absolute() and Path(part).resolve() == bin_directory
        for part in initial_path.split(os.pathsep)
    ):
        print(f"Warning: {bin_directory} is not in the initial PATH of your terminal.")
        print("Ubuntu's default profile adds it on login when the folder exists. Log out and back in.")
        print('For this terminal only: export PATH="$HOME/.local/bin:$PATH"')
        print("No shell profiles were modified.")
    selected = shutil.which("chopper", path=initial_path)
    if selected is not None and Path(selected).resolve() != destination.resolve():
        print(f"Warning: another command shadows Chopper in the initial PATH: {selected}")


def install_integrations(launcher: Path, *, initial_path: str) -> int:
    launcher = _absolute(launcher).resolve(strict=True)
    desktop_entry(launcher)
    project = launcher.parent
    load_receipt(project)
    home = _absolute(Path.home()).resolve()
    configured = os.environ.get("XDG_DATA_HOME")
    data_home = _absolute(Path(configured) if configured else home / ".local" / "share").resolve()
    menu = data_home / "applications" / "chopper.desktop"
    want_menu = _confirm(menu, project, "Create or update the Chopper menu entry there?")
    command = home / ".local" / "bin" / "chopper"
    want_command = _confirm(command, project, "Create the global Chopper command link there?")
    icon_destination = data_home / "icons/hicolor/scalable/apps/chopper.svg"
    want_icon = _confirm(icon_destination, project, "Install or update the dedicated Chopper icon there?")
    desktop_dir = _desktop_directory(home)
    want_desktop = desktop_dir is not None and _confirm(
        desktop_dir / "chopper.desktop",
        project,
        "Create or update the executable KDE Desktop shortcut there?",
    )
    icon = install_icon(launcher, data_home=data_home) if want_icon else None
    print(
        f"Icon installed: {icon}" if icon else "Dedicated icon skipped; shortcuts use the generic audio icon."
    )
    if want_menu:
        print(f"Menu entry installed: {_install_menu(launcher, data_home, icon)}")
    else:
        print("Menu entry skipped. You can still start ./chopper.")
    if want_command:
        print(f"Global command installed: {install_global_command(launcher, home=home)}")
        _report_path(home, initial_path, command)
    else:
        print("Global command skipped. You can still start ./chopper.")
    if want_desktop:
        assert desktop_dir is not None
        installed = install_desktop_copy(launcher, desktop_dir=desktop_dir, icon=icon)
        print(f"Desktop shortcut installed: {installed}")
    else:
        print("Desktop shortcut skipped. No Desktop folder was created.")
    return 0


def uninstall_integrations(project: Path) -> int:
    """Remove only proven integrations, after consent; keep all user/project data."""
    try:
        project = _absolute(project).resolve(strict=True)
        with _project_lock(project):
            return _uninstall_locked(project)
    except (OSError, ValueError) as error:
        print(
            f"Uninstall error: {error}. Unproven integrations and user data are preserved.", file=sys.stderr
        )
        return 1


def _uninstall_locked(project: Path) -> int:
    data, receipt_before = _read_receipt(project)
    if receipt_before is None:
        print("No installation receipt; nothing to remove. No files were changed.")
        return 0
    receipt = project / RECEIPT_NAME
    removable = []
    absent = []
    conflicts = False
    print(f"Project: {project}\nOwnership receipt: {receipt}")
    print("Project, local launcher, .venv, uv, system packages, profiles, settings, cache and audio stay.")
    for role, record in data["artifacts"].items():
        path = Path(record["path"])
        try:
            current = _stamp(path)
            if current is None:
                absent.append(role)
                print(f"Already absent: {path}")
            elif current == record:
                removable.append(role)
                print(f"Proven integration to remove: {path}")
            else:
                raise ValueError("identity, parent, content or permissions changed")
        except (OSError, ValueError) as error:
            conflicts = True
            print(f"Preserved {role}: {path} ({error})", file=sys.stderr)
    print("No parent folders will be removed. The receipt is removed only if no artifacts remain.")
    try:
        agreed = input("Remove the proven integrations and update their receipt? [y/N] ").strip().lower()
    except EOFError:
        agreed = ""
    if agreed not in {"y", "yes"}:
        print("Uninstall skipped. No files were changed.")
        return int(conflicts)
    if _stamp(receipt) != receipt_before:
        raise FileExistsError("Receipt changed while awaiting consent; nothing removed.")
    for role in absent + removable:
        record = data["artifacts"][role]
        path = Path(record["path"])
        try:
            # Recheck after consent: a replacement, even identical, is not ours.
            current = _stamp(path)
            if current is not None:
                if current != record:
                    raise FileExistsError("Integration changed while awaiting removal")
                path.unlink()
                print(f"Removed: {path}")
            del data["artifacts"][role]
        except (OSError, ValueError) as error:
            conflicts = True
            print(f"Preserved {role}: {path} ({error})", file=sys.stderr)
    if data["artifacts"]:
        original, _ = _read_receipt(project)
        if data != original:
            _save_receipt(project, data, receipt_before)
        print(f"Receipt retained for remaining integrations: {receipt}")
    else:
        if _stamp(receipt) != receipt_before:
            raise FileExistsError("Receipt changed; preserving it.")
        receipt.unlink()
        print(f"Removed unused receipt: {receipt}")
    return int(conflicts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--initial-path")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--project", type=Path)
    args = parser.parse_args()
    if args.uninstall:
        if args.project is None or args.launcher is not None or args.initial_path is not None:
            parser.error("--uninstall requires --project only")
        return uninstall_integrations(args.project)
    if args.launcher is None or args.initial_path is None or args.project is not None:
        parser.error("installation requires --launcher and --initial-path only")
    try:
        return install_integrations(args.launcher, initial_path=args.initial_path)
    except (OSError, ValueError) as error:
        print(f"Integration error: {error}. The local ./chopper launcher remains available.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
