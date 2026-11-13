"""Build a traceable source ZIP from a clean, committed Chopper checkout."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

REQUIRED_FILES = {
    "install.sh",
    "scripts/install_desktop.py",
    "pyproject.toml",
    "uv.lock",
    "LICENSE",
    "README.md",
    "docs/INSTALL_KUBUNTU.md",
    "docs/FINAL_VALIDATION.md",
    "src/chopper/__init__.py",
    "src/chopper/app.py",
    "src/chopper/py.typed",
}


def _git(repo: Path, *args: str) -> bytes:
    # Hooks export their own index/worktree context; only the explicit repo is ours.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout


def _clean_commit(repo: Path) -> str:
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=no", "--ignore-submodules=none"):
        raise ValueError(
            "Release requires a clean tracked working tree and index; commit your changes first."
        )
    return _git(repo, "rev-parse", "HEAD").decode().strip()


def _committed_files(repo: Path, commit: str) -> dict[str, tuple[int, bytes]]:
    files: dict[str, tuple[int, bytes]] = {}
    for record in _git(repo, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not record:
            continue
        header, raw_name = record.split(b"\t", 1)
        name = raw_name.decode("utf-8")
        if name not in REQUIRED_FILES and not name.startswith("src/chopper/"):
            continue
        mode, kind, object_id = header.split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise ValueError(f"Release refuses a symlink or non-regular tracked file: {name}")
        parts = PurePosixPath(name).parts
        if "\\" in name or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ValueError(f"Unsafe archive path: {name!r}")
        if name.startswith("src/chopper/") and (
            any(part.startswith(".") or part == "__pycache__" for part in parts)
            or (not name.endswith(".py") and name != "src/chopper/py.typed")
        ):
            raise ValueError(f"Unexpected tracked source data; review the release allowlist: {name}")
        files[name] = (int(mode, 8), _git(repo, "cat-file", "blob", object_id.decode("ascii")))
    missing = REQUIRED_FILES - files.keys()
    if missing:
        raise ValueError(f"Required release files missing: {', '.join(sorted(missing))}")
    return files


def _same_output(path: Path, expected: bytes) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(mode) or path.read_bytes() != expected:
        raise ValueError(f"Refusing to overwrite an unrelated release output: {path}")
    return True


def build_release(repo: Path) -> tuple[Path, Path]:
    """Create ZIP and SHA-256; preserve foreign files and identical prior builds."""
    repo = repo.resolve(strict=True)
    top = Path(_git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if repo != top:
        raise ValueError("The release directory must be the repository root.")
    commit = _clean_commit(repo)
    files = _committed_files(repo, commit)
    project = tomllib.loads(files["pyproject.toml"][1].decode("utf-8")).get("project", {})
    version = project.get("version") if isinstance(project, dict) else None
    if (
        not isinstance(version, str)
        or len(version) > 80
        or not re.fullmatch(r"[0-9][A-Za-z0-9.+-]*", version)
    ):
        raise ValueError("Project version must be a safe, nonempty version string starting with a digit.")
    root = f"chopper-{version}-{commit[:12]}-linux"
    files["RELEASE.txt"] = (
        0o100644,
        (
            f"Chopper {version}\nSource commit: {commit}\n"
            "Source distribution with an online installer; dependencies are not bundled.\n"
            "Initial target: Kubuntu 26.04.1; verify on the actual target machine.\n"
            "Installation: see docs/INSTALL_KUBUNTU.md and run bash install.sh.\n"
        ).encode(),
    )
    dist = repo / "dist"
    if dist.is_symlink() or (dist.exists() and not dist.is_dir()):
        raise ValueError("Release dist must be a real directory inside the repository, not a symlink.")
    dist.mkdir(exist_ok=True)
    archive = dist / f"{root}.zip"
    checksum = dist / f"{root}.zip.sha256"
    temporary: list[Path] = []
    published: list[tuple[Path, Path]] = []
    try:
        for _ in range(2):
            descriptor, name = tempfile.mkstemp(prefix=".chopper-release-", dir=dist)
            temporary.append(Path(name))
            os.close(descriptor)
        with zipfile.ZipFile(temporary[0], "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, (mode, content) in sorted(files.items()):
                info = zipfile.ZipInfo(f"{root}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = mode << 16
                bundle.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        archive_bytes = temporary[0].read_bytes()
        checksum_bytes = f"{hashlib.sha256(archive_bytes).hexdigest()}  {archive.name}\n".encode("ascii")
        temporary[1].write_bytes(checksum_bytes)
        # Check both targets before publishing either, including checksum collisions.
        _same_output(archive, archive_bytes)
        _same_output(checksum, checksum_bytes)
        if _clean_commit(repo) != commit:
            raise ValueError("Repository changed during the release; retry from a clean commit.")
        for source, destination, content in (
            (temporary[0], archive, archive_bytes),
            (temporary[1], checksum, checksum_bytes),
        ):
            if not _same_output(destination, content):
                os.link(source, destination)
                published.append((destination, source))
        return archive, checksum
    except BaseException:
        # Roll back only hard links created by this call, never somebody else's file.
        for destination, source in reversed(published):
            try:
                if os.path.samestat(destination.lstat(), source.stat()):
                    destination.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)


def main() -> int:
    try:
        archive, checksum = build_release(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Release error: {error}", file=sys.stderr)
        return 1
    print(f"Archive: {archive}\nSHA-256: {checksum}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
