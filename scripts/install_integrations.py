"""Install optional user integrations with consent and a local ownership receipt."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import stat
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
        if role not in {"global-command", "menu"} or not isinstance(record, dict):
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
            destination.name != "chopper.desktop"
            or destination.parent.name != "applications"
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


def _install_menu(launcher: Path, data_home: Path) -> Path:
    launcher = _absolute(launcher).resolve(strict=True)
    with _project_lock(launcher.parent):
        return _install_menu_locked(launcher, data_home)


def _install_menu_locked(launcher: Path, data_home: Path) -> Path:
    project = launcher.parent
    content = desktop_entry(launcher).encode("utf-8")
    data, receipt_before = _read_receipt(project)
    destination = data_home / "applications" / "chopper.desktop"
    previous = data["artifacts"].get("menu")
    current = _stamp(destination)
    created_here = current is None
    if previous is not None and (
        previous["path"] != str(destination) or (current is not None and previous != current)
    ):
        raise ValueError(f"Refusing to overwrite an unowned or modified menu entry: {destination}")
    if current is not None:
        if current["type"] != "file" or destination.read_bytes() != content or current["mode"] != 0o644:
            raise ValueError(f"Refusing to overwrite an unrelated menu entry: {destination}")
        if previous is not None:
            return destination
        # Adopt only the exact historical entry for this launcher, not a marker alone.
    else:
        current = _publish_bytes(destination, content, 0o644, None)
    assert current is not None
    data["artifacts"]["menu"] = current
    try:
        _save_receipt(project, data, receipt_before)
    except (OSError, ValueError):
        if created_here:
            _rollback_created(destination, current)
        raise
    return destination


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
    if _confirm(menu, project, "Create or update the Chopper menu entry there?"):
        print(f"Menu entry installed: {_install_menu(launcher, data_home)}")
    else:
        print("Menu entry skipped. You can still start ./chopper.")
    command = home / ".local" / "bin" / "chopper"
    if _confirm(command, project, "Create the global Chopper command link there?"):
        print(f"Global command installed: {install_global_command(launcher, home=home)}")
        _report_path(home, initial_path, command)
    else:
        print("Global command skipped. You can still start ./chopper.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", required=True, type=Path)
    parser.add_argument("--initial-path", required=True)
    args = parser.parse_args()
    try:
        return install_integrations(args.launcher, initial_path=args.initial_path)
    except (OSError, ValueError) as error:
        print(f"Integration error: {error}. The local ./chopper launcher remains available.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
