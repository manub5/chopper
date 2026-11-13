import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

BUILDER = Path(__file__).parents[1] / "scripts/build_release.py"


def release_tool():
    spec = importlib.util.spec_from_file_location("build_release", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        ["git", "-c", f"core.hooksPath={repo / '.git/no-hooks'}", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


@pytest.fixture
def release_repo(tmp_path):
    repo = tmp_path / "release project"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Release test")
    git(repo, "config", "user.email", "release@example.invalid")
    for name, content in {
        "pyproject.toml": '[project]\nname = "chopper"\nversion = "0.1.0"\n',
        "uv.lock": "lock fixture: preserve these exact bytes\n",
        "LICENSE": "License fixture — exact content\n",
        "README.md": "# Chopper\n",
        "install.sh": "#!/bin/bash\nexit 0\n",
        "scripts/install_desktop.py": '"""Desktop helper fixture."""\n',
        "src/chopper/__init__.py": "",
        "src/chopper/app.py": '"""App fixture."""\n',
        "src/chopper/py.typed": "",
        "docs/INSTALL_KUBUNTU.md": "# Installation\n",
        "docs/FINAL_VALIDATION.md": "# Manual checks\n",
        ".gitignore": ".env\n.venv/\ndist/\n*.wav\n",
    }.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (repo / "install.sh").chmod(0o755)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Fixture")
    return repo


def test_release_has_single_root_exact_blobs_and_matching_checksum(release_repo):
    tool = release_tool()
    repo = release_repo
    commit = git(repo, "rev-parse", "HEAD")
    archive, checksum = tool.build_release(repo)
    root = f"chopper-0.1.0-{commit[:12]}-linux"
    assert archive == repo / "dist" / f"{root}.zip"
    assert checksum == repo / "dist" / f"{root}.zip.sha256"
    assert checksum.read_text() == f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n"
    with zipfile.ZipFile(archive) as bundle:
        assert {name.split("/")[0] for name in bundle.namelist()} == {root}
        assert {name.removeprefix(root + "/") for name in bundle.namelist()} == {
            "pyproject.toml",
            "uv.lock",
            "LICENSE",
            "README.md",
            "install.sh",
            "scripts/install_desktop.py",
            "src/chopper/__init__.py",
            "src/chopper/app.py",
            "src/chopper/py.typed",
            "docs/INSTALL_KUBUNTU.md",
            "docs/FINAL_VALIDATION.md",
            "RELEASE.txt",
        }
        assert bundle.read(f"{root}/LICENSE") == "License fixture — exact content\n".encode()
        assert bundle.read(f"{root}/uv.lock") == b"lock fixture: preserve these exact bytes\n"
        metadata = bundle.read(f"{root}/RELEASE.txt").decode()
        assert commit in metadata and "0.1.0" in metadata
        assert bundle.getinfo(f"{root}/install.sh").external_attr >> 16 == 0o100755
        assert bundle.testzip() is None
    assert git(repo, "status", "--porcelain", "--untracked-files=no") == ""


@pytest.mark.parametrize("key", ["GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE"])
def test_builder_ignores_git_context_inherited_from_parent_hook(release_repo, tmp_path, monkeypatch, key):
    tool = release_tool()
    foreign = tmp_path / "foreign-git-context"
    monkeypatch.setenv(key, str(foreign))
    archive, checksum = tool.build_release(release_repo)
    assert archive.is_file() and checksum.is_file()
    assert not foreign.exists()


def test_untracked_and_unrelated_tracked_files_are_not_shipped(release_repo):
    tool = release_tool()
    repo = release_repo
    (repo / "internal-notes.txt").write_text("not for distribution")
    git(repo, "add", "internal-notes.txt")
    git(repo, "commit", "-qm", "Unrelated tracked file")
    for name in (".env", "recording.wav", ".venv/private", "dist/old.zip", "src/chopper/untracked.py"):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private fixture sentinel")
    archive, _ = tool.build_release(repo)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert not any(b"private fixture sentinel" in bundle.read(name) for name in names)
        assert not any("internal-notes" in name or "/.git/" in name or "/dist/" in name for name in names)


@pytest.mark.parametrize("state", ["unstaged", "staged", "deleted"])
def test_dirty_tracked_tree_is_rejected_before_creating_dist(release_repo, state):
    tool = release_tool()
    readme = release_repo / "README.md"
    if state == "deleted":
        readme.unlink()
    else:
        readme.write_text("changed")
    if state == "staged":
        git(release_repo, "add", "README.md")
    with pytest.raises(ValueError, match="clean"):
        tool.build_release(release_repo)
    assert not (release_repo / "dist").exists()


@pytest.mark.parametrize("version", ["../escape", "1/escape", "1\\escape", "", "-bad", "1\nnew"])
def test_unsafe_version_cannot_escape_dist(release_repo, version):
    tool = release_tool()
    (release_repo / "pyproject.toml").write_text(f"[project]\nversion = {json.dumps(version)}\n")
    git(release_repo, "add", "pyproject.toml")
    git(release_repo, "commit", "-qm", "Unsafe version fixture")
    with pytest.raises(ValueError, match="version"):
        tool.build_release(release_repo)
    assert not (release_repo / "dist").exists()


@pytest.mark.parametrize("name", ["src/chopper/app.py", "scripts/install_desktop.py", "LICENSE"])
def test_tracked_symlink_is_rejected_not_dereferenced(release_repo, tmp_path, name):
    tool = release_tool()
    target = tmp_path / "private-target"
    target.write_text("keep this private sentinel")
    path = release_repo / name
    path.unlink()
    path.symlink_to(target)
    git(release_repo, "add", name)
    git(release_repo, "commit", "-qm", "Symlink fixture")
    with pytest.raises(ValueError):
        tool.build_release(release_repo)
    assert target.read_text() == "keep this private sentinel"
    assert not (release_repo / "dist").exists()


@pytest.mark.parametrize(
    "name", ["src/chopper/.env", "src/chopper/recording.wav", "src/chopper/.venv/private.py"]
)
def test_unexpected_tracked_source_data_is_rejected(release_repo, name):
    tool = release_tool()
    path = release_repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("private fixture sentinel")
    git(release_repo, "add", "-f", name)
    git(release_repo, "commit", "-qm", "Unexpected source data")
    with pytest.raises(ValueError):
        tool.build_release(release_repo)
    assert not (release_repo / "dist").exists()


def test_missing_required_file_fails_without_deliverables(release_repo):
    tool = release_tool()
    git(release_repo, "rm", "uv.lock")
    git(release_repo, "commit", "-qm", "Missing lock fixture")
    with pytest.raises(ValueError, match=r"uv\.lock"):
        tool.build_release(release_repo)
    assert not (release_repo / "dist").exists()


def test_repeated_build_is_byte_reproducible_and_does_not_rewrite_outputs(release_repo):
    tool = release_tool()
    archive, checksum = tool.build_release(release_repo)
    previous = (archive.read_bytes(), checksum.read_bytes())
    modified = (archive.stat().st_mtime_ns, checksum.stat().st_mtime_ns)
    assert tool.build_release(release_repo) == (archive, checksum)
    assert (archive.read_bytes(), checksum.read_bytes()) == previous
    assert (archive.stat().st_mtime_ns, checksum.stat().st_mtime_ns) == modified
    archive.unlink()
    checksum.unlink()
    tool.build_release(release_repo)
    assert (archive.read_bytes(), checksum.read_bytes()) == previous


@pytest.mark.parametrize("kind", ["zip", "checksum", "symlink", "directory"])
def test_existing_foreign_output_is_never_overwritten(release_repo, tmp_path, kind):
    tool = release_tool()
    commit = git(release_repo, "rev-parse", "HEAD")
    dist = release_repo / "dist"
    dist.mkdir()
    archive = dist / f"chopper-0.1.0-{commit[:12]}-linux.zip"
    checksum = archive.with_suffix(".zip.sha256")
    target = checksum if kind == "checksum" else archive
    foreign = tmp_path / "foreign-file"
    foreign.write_text("keep this sentinel")
    if kind == "symlink":
        target.symlink_to(foreign)
    elif kind == "directory":
        target.mkdir()
    else:
        target.write_text("keep this sentinel")
    with pytest.raises((ValueError, OSError)):
        tool.build_release(release_repo)
    assert foreign.read_text() == "keep this sentinel"
    if kind != "directory":
        assert target.read_text() == "keep this sentinel"
    assert list(dist.iterdir()) == [target]


def test_symlink_dist_does_not_write_outside_repository(release_repo, tmp_path):
    tool = release_tool()
    outside = tmp_path / "outside"
    outside.mkdir()
    (release_repo / "dist").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        tool.build_release(release_repo)
    assert list(outside.iterdir()) == []


def test_failed_checksum_publication_removes_only_own_partial_zip(release_repo, monkeypatch):
    tool = release_tool()
    real_link = tool.os.link

    def fail_checksum(source, destination):
        if str(destination).endswith(".sha256"):
            raise PermissionError("simulated publication failure")
        real_link(source, destination)

    monkeypatch.setattr(tool.os, "link", fail_checksum)
    with pytest.raises(PermissionError):
        tool.build_release(release_repo)
    assert list((release_repo / "dist").iterdir()) == []


def test_cli_builds_from_its_repository_even_with_another_cwd(release_repo, tmp_path):
    path = release_repo / "scripts/build_release.py"
    path.write_bytes(BUILDER.read_bytes())
    git(release_repo, "add", "scripts/build_release.py")
    git(release_repo, "commit", "-qm", "Builder fixture")
    result = subprocess.run(
        [sys.executable, str(path)], cwd=tmp_path, capture_output=True, text=True, check=False, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert len(list((release_repo / "dist").glob("*.zip"))) == 1
    assert ".zip.sha256" in result.stdout
