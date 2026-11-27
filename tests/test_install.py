import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


def write_tool(path, content):
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + content)
    path.chmod(0o755)


def run_installer(project, env, *, answers="", cwd=None):
    return subprocess.run(
        ["bash", str(project / "install.sh")],
        env=env,
        cwd=cwd,
        input=answers,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


@pytest.fixture
def installer_sandbox(tmp_path):
    project = tmp_path / "project with spaces ' $cash %sample"
    project.mkdir()
    shutil.copyfile(Path(__file__).parents[1] / "install.sh", project / "install.sh")
    helper = Path(__file__).parents[1] / "scripts/install_desktop.py"
    if helper.exists():
        (project / "scripts").mkdir()
        shutil.copyfile(helper, project / "scripts/install_desktop.py")
    integrations = Path(__file__).parents[1] / "scripts/install_integrations.py"
    if integrations.exists():
        shutil.copyfile(integrations, project / "scripts/install_integrations.py")
    icon = Path(__file__).parents[1] / "assets/chopper.svg"
    if icon.exists():
        (project / "assets").mkdir()
        shutil.copyfile(icon, project / "assets/chopper.svg")
    tools = tmp_path / "tools"
    tools.mkdir()
    uv_content = """if [[ "${1:-}" == --version ]]; then
    printf 'uv test\n'
    exit 0
fi
printf '%s\\n' "$@" >> "$UV_CALLS"
[[ "${UV_STATUS:-0}" == 0 ]] || exit "$UV_STATUS"
environment="${UV_PROJECT_ENVIRONMENT:-.venv}"
mkdir -p "$environment/bin"
ln -sf "$TEST_PYTHON" "$environment/bin/python"
if [[ "${OMIT_APP:-0}" == 0 ]]; then
    cat > "$environment/bin/chopper" <<'APP'
#!/usr/bin/env bash
printf '%s\\n' "$PWD" "$@" >> "$APP_CALLS"
APP
    chmod +x "$environment/bin/chopper"
fi
"""
    write_tool(tmp_path / "uv-template", uv_content)
    for name, content in {
        "uv": uv_content,
        "uname": 'printf "Linux\\n"\n',
        "dpkg": 'exit "${PACKAGES_MISSING:-0}"\n',
        "apt-get": 'printf "apt-get %s\\n" "$*" >> "$EXTERNAL_CALLS"\nexit "${APT_STATUS:-0}"\n',
        "sudo": 'printf "sudo %s\\n" "$*" >> "$EXTERNAL_CALLS"\n"$@"\n',
        "curl": """printf 'curl\\n' >> "$EXTERNAL_CALLS"
output=''
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output) output="$2"; shift 2 ;;
        *) shift ;;
    esac
done
payload='printf "executed\\n" >> "$UV_INSTALL_EXECUTED"
mkdir -p "$HOME/.local/bin"
cp "$UV_TEMPLATE" "$HOME/.local/bin/uv"
chmod +x "$HOME/.local/bin/uv"'
if [[ -n "$output" ]]; then
    printf '%s\\n' "$payload" > "$output"
else
    printf '%s\\n' "$payload"
fi
exit "${CURL_STATUS:-0}"
""",
    }.items():
        write_tool(tools / name, content)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "PATH": f"{tools}:/usr/bin:/bin",
        "HOME": str(home),
        "UV_CALLS": str(tmp_path / "uv-calls"),
        "APP_CALLS": str(tmp_path / "app-calls"),
        "EXTERNAL_CALLS": str(tmp_path / "external-calls"),
        "UV_INSTALL_EXECUTED": str(tmp_path / "uv-install-executed"),
        "UV_TEMPLATE": str(tmp_path / "uv-template"),
        "TMPDIR": str(tmp_path),
        "TEST_PYTHON": sys.executable,
        "XDG_DATA_HOME": str(tmp_path / "desktop-data"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    for key in ("UV_CALLS", "APP_CALLS", "EXTERNAL_CALLS"):
        Path(env[key]).touch()
    (project / "uv.lock").write_text("locked-dependencies-sentinel")
    old = project / "choppeur"
    old.write_text("old launcher sentinel")
    return project, env


def test_installer_generates_chopper_and_launcher_preserves_arguments(installer_sandbox, tmp_path):
    project, env = installer_sandbox
    result = run_installer(project, env, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    launcher = project / "chopper"
    assert launcher.is_file() and os.access(launcher, os.X_OK)
    assert (project / "choppeur").read_text() == "old launcher sentinel"
    assert Path(env["UV_CALLS"]).read_text().splitlines() == [
        "sync",
        "--project",
        str(project),
        "--locked",
        "--no-dev",
        "--inexact",
    ]
    assert (project / "uv.lock").read_text() == "locked-dependencies-sentinel"
    Path(env["UV_CALLS"]).write_text("")
    subprocess.run(
        [str(launcher), "--test", "argument with spaces"],
        env=env,
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert Path(env["APP_CALLS"]).read_text().splitlines() == [
        str(tmp_path),
        "--test",
        "argument with spaces",
    ]
    assert Path(env["UV_CALLS"]).read_text() == ""
    # Re-running an installation must safely update its own generated launcher.
    assert run_installer(project, env, cwd=tmp_path).returncode == 0
    assert (project / "choppeur").read_text() == "old launcher sentinel"


@pytest.mark.parametrize("kind", ["file", "symlink", "broken-symlink", "directory"])
def test_installer_refuses_to_overwrite_unrelated_launcher(installer_sandbox, tmp_path, kind):
    project, env = installer_sandbox
    target = tmp_path / "user-script"
    target.write_text("keep this unrelated file")
    launcher = project / "chopper"
    if kind == "broken-symlink":
        launcher.symlink_to(tmp_path / "missing")
    elif kind == "symlink":
        launcher.symlink_to(target)
    elif kind == "directory":
        launcher.mkdir()
    else:
        launcher.write_bytes(target.read_bytes())
    result = run_installer(project, env, answers="y\ny\n", cwd=tmp_path)
    assert result.returncode != 0
    assert "refusing" in (result.stderr + result.stdout).lower()
    assert target.read_text() == "keep this unrelated file"
    if kind in {"file", "symlink"}:
        assert launcher.read_text() == target.read_text()
    assert Path(env["UV_CALLS"]).read_text() == ""
    assert Path(env["EXTERNAL_CALLS"]).read_text() == ""


@pytest.mark.parametrize("answers", ["n\n", "", "\n"])
def test_installer_requires_consent_before_installing_uv(installer_sandbox, answers):
    project, env = installer_sandbox
    (Path(env["PATH"].split(":")[0]) / "uv").unlink()
    result = run_installer(project, env, answers=answers)
    assert result.returncode != 0
    assert Path(env["EXTERNAL_CALLS"]).read_text() == ""
    assert not (Path(env["HOME"]) / ".local").exists()
    assert not (project / "chopper").exists()


def test_installer_downloads_uv_only_after_consent(installer_sandbox):
    project, env = installer_sandbox
    (Path(env["PATH"].split(":")[0]) / "uv").unlink()
    result = run_installer(project, env, answers="y\n")
    assert result.returncode == 0, result.stderr
    assert str(Path(env["HOME"]) / ".local/bin") in result.stdout
    assert Path(env["UV_INSTALL_EXECUTED"]).read_text() == "executed\n"
    assert (project / "chopper").is_file()
    assert Path(env["EXTERNAL_CALLS"]).read_text() == "curl\n"


def test_failed_uv_download_does_not_execute_partial_installer(installer_sandbox):
    project, env = installer_sandbox
    (Path(env["PATH"].split(":")[0]) / "uv").unlink()
    result = run_installer(project, {**env, "CURL_STATUS": "23"}, answers="y\n")
    assert result.returncode != 0
    assert not Path(env["UV_INSTALL_EXECUTED"]).exists()
    assert not (project / "chopper").exists()
    assert "Done." not in result.stdout


@pytest.mark.parametrize("answers", ["n\n", "", "\n"])
def test_installer_requires_consent_before_sudo(installer_sandbox, answers):
    project, env = installer_sandbox
    result = run_installer(project, {**env, "PACKAGES_MISSING": "1"}, answers=answers)
    assert result.returncode != 0
    assert Path(env["EXTERNAL_CALLS"]).read_text() == ""
    assert Path(env["UV_CALLS"]).read_text() == ""
    assert not (project / "chopper").exists()


@pytest.mark.parametrize("status", ["0", "42"])
def test_installer_handles_consented_system_install_result(installer_sandbox, status):
    project, env = installer_sandbox
    result = run_installer(project, {**env, "PACKAGES_MISSING": "1", "APT_STATUS": status}, answers="y\n")
    calls = Path(env["EXTERNAL_CALLS"]).read_text().splitlines()
    assert calls[:2] == ["sudo apt-get update", "apt-get update"]
    if status == "0":
        assert result.returncode == 0, result.stderr
        assert calls[2:] == [
            "sudo apt-get install -y ffmpeg libportaudio2",
            "apt-get install -y ffmpeg libportaudio2",
        ]
        assert (project / "chopper").is_file()
    else:
        assert result.returncode != 0
        assert len(calls) == 2
        assert not (project / "chopper").exists()
        assert "Done." not in result.stdout


def test_sync_failure_keeps_old_launcher_and_files(installer_sandbox):
    project, env = installer_sandbox
    launcher = project / "chopper"
    previous = "#!/bin/bash\n# Generated by install.sh for Chopper.\nprintf old\n"
    launcher.write_text(previous)
    result = run_installer(project, {**env, "UV_STATUS": "37"})
    assert result.returncode != 0
    assert launcher.read_text() == previous
    assert (project / "uv.lock").read_text() == "locked-dependencies-sentinel"
    assert "Done." not in result.stdout


def test_sync_failure_does_not_generate_launcher(installer_sandbox):
    project, env = installer_sandbox
    result = run_installer(project, {**env, "UV_STATUS": "37"})
    assert result.returncode != 0
    assert not (project / "chopper").exists()
    assert "Done." not in result.stdout


def test_incomplete_environment_does_not_report_success(installer_sandbox):
    project, env = installer_sandbox
    result = run_installer(project, {**env, "OMIT_APP": "1"})
    assert result.returncode != 0
    assert not (project / "chopper").exists()
    assert "Done." not in result.stdout


def test_installer_keeps_environment_inside_selected_folder(installer_sandbox, tmp_path):
    project, env = installer_sandbox
    unrelated_environment = tmp_path / "other-environment"
    result = run_installer(project, {**env, "UV_PROJECT_ENVIRONMENT": str(unrelated_environment)})
    assert result.returncode == 0, result.stderr
    assert (project / ".venv/bin/chopper").is_file()
    assert not unrelated_environment.exists()


def test_inherited_uv_project_cannot_bypass_chopper_lock_validation(installer_sandbox, tmp_path):
    project, env = installer_sandbox
    uv = shutil.which("uv")
    assert uv is not None
    tools_uv = Path(env["PATH"].split(":")[0]) / "uv"
    tools_uv.unlink()
    tools_uv.symlink_to(uv)
    foreign = tmp_path / "unrelated-project"
    foreign.mkdir()
    metadata = '[project]\nname = "unrelated"\nversion = "0.1.0"\nrequires-python = ">=3.12,<3.13"\n'
    (foreign / "pyproject.toml").write_text(metadata)
    (project / "pyproject.toml").write_text(metadata.replace('"unrelated"', '"chopper"'))
    offline_env = {
        **env,
        "UV_OFFLINE": "1",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "UV_PYTHON": sys.executable,
    }
    subprocess.run(
        [uv, "lock", "--project", str(foreign)], env=offline_env, check=True, capture_output=True, timeout=30
    )
    subprocess.run(
        [uv, "venv", "--python", sys.executable, str(project / ".venv")],
        env=offline_env,
        check=True,
        capture_output=True,
        timeout=30,
    )
    write_tool(project / ".venv/bin/chopper", "exit 0\n")
    result = run_installer(project, {**offline_env, "UV_PROJECT": str(foreign)})
    assert result.returncode != 0, result.stdout
    assert "uv.lock" in result.stderr
    assert "Done." not in result.stdout
    assert (project / "uv.lock").read_text() == "locked-dependencies-sentinel"


def test_launcher_reports_missing_environment_without_running_uv(installer_sandbox):
    project, env = installer_sandbox
    assert run_installer(project, env).returncode == 0
    (project / ".venv/bin/chopper").unlink()
    Path(env["UV_CALLS"]).write_text("")
    result = subprocess.run(
        [str(project / "chopper")], env=env, capture_output=True, text=True, check=False, timeout=10
    )
    assert result.returncode != 0
    assert "install.sh" in result.stderr
    assert Path(env["UV_CALLS"]).read_text() == ""


def test_installer_offers_real_desktop_helper_after_success(installer_sandbox):
    project, env = installer_sandbox
    result = run_installer(project, env, answers="y\n")
    assert result.returncode == 0, result.stderr
    destination = Path(env["XDG_DATA_HOME"]) / "applications/chopper.desktop"
    assert destination.is_file()
    assert str(destination) in result.stdout
    assert "Chopper" in destination.read_text()


def test_installer_skips_shortcut_without_consent(installer_sandbox):
    project, env = installer_sandbox
    result = run_installer(project, env, answers="n\n")
    assert result.returncode == 0, result.stderr
    assert "skipped" in result.stdout.lower()
    assert not Path(env["XDG_DATA_HOME"]).exists()
    assert (project / "chopper").is_file()


def test_installer_propagates_desktop_error_without_losing_local_launcher(installer_sandbox):
    project, env = installer_sandbox
    Path(env["XDG_DATA_HOME"]).write_text("foreign file sentinel")
    result = run_installer(project, env, answers="y\n")
    assert result.returncode != 0
    assert "Done." not in result.stdout
    assert (project / "chopper").is_file()
    assert Path(env["XDG_DATA_HOME"]).read_text() == "foreign file sentinel"


def test_global_symlink_launches_project_from_other_cwd(installer_sandbox, tmp_path):
    project, env = installer_sandbox
    result = run_installer(project, env, answers="n\ny\n")
    assert result.returncode == 0, result.stderr
    link = Path(env["HOME"]) / ".local/bin/chopper"
    assert link.is_symlink() and os.readlink(link) == str(project / "chopper")
    Path(env["UV_CALLS"]).write_text("")
    subprocess.run(
        [str(link), "--probe", "argument $ with % spaces"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert Path(env["APP_CALLS"]).read_text().splitlines() == [
        str(tmp_path),
        "--probe",
        "argument $ with % spaces",
    ]
    assert Path(env["UV_CALLS"]).read_text() == ""


def test_launcher_follows_symlink_chain_and_preserves_args(installer_sandbox, tmp_path):
    project, env = installer_sandbox
    assert run_installer(project, env).returncode == 0
    second = tmp_path / "second link"
    second.symlink_to(project / "chopper")
    first = tmp_path / "first link"
    first.symlink_to(second.name)
    Path(env["UV_CALLS"]).write_text("")
    subprocess.run(
        [str(first), "arg with spaces", "x$y%z"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert Path(env["APP_CALLS"]).read_text().splitlines() == [str(tmp_path), "arg with spaces", "x$y%z"]
    assert Path(env["UV_CALLS"]).read_text() == ""


def test_path_warning_uses_parent_path_before_uv_bootstrap(installer_sandbox):
    project, env = installer_sandbox
    home = Path(env["HOME"])
    (home / ".profile").write_text("profile sentinel\n")
    (home / ".bashrc").write_text("bashrc sentinel\n")
    (Path(env["PATH"].split(":")[0]) / "uv").unlink()
    result = run_installer(project, env, answers="y\nn\ny\n")
    assert result.returncode == 0, result.stderr
    assert (home / ".local/bin/chopper").is_symlink()
    assert "not in the initial PATH" in result.stdout
    assert 'export PATH="$HOME/.local/bin:$PATH"' in result.stdout
    assert (home / ".profile").read_text() == "profile sentinel\n"
    assert (home / ".bashrc").read_text() == "bashrc sentinel\n"


def test_real_git_pull_updates_command_menu_and_desktop_without_reinstall(installer_sandbox, tmp_path):
    project, env = installer_sandbox
    desktop = tmp_path / "XDG Desktop"
    desktop.mkdir()
    tools = Path(env["PATH"].split(":")[0])
    write_tool(tools / "xdg-user-dir", f"printf '%s\\n' '{desktop}'\n")
    output = tmp_path / "version-output"
    env["CHOPPER_PROBE_OUTPUT"] = str(output)
    code = project / "probe.py"
    code.write_text(
        "import os\nfrom pathlib import Path\n"
        "Path(os.environ['CHOPPER_PROBE_OUTPUT']).write_text('version-one')\n"
    )
    (project / ".gitignore").write_text(
        ".env\n*.key\n*.pem\nbuild/\ndist/\n.venv/\n.chopper-install.json\n/chopper\n"
    )
    git_env = {key: value for key, value in env.items() if not key.startswith("GIT_")}
    git_env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def git(where, *args):
        return subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=Update test",
                "-c",
                "user.email=test@example.invalid",
                *args,
            ],
            cwd=where,
            env=git_env,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout

    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(project, "init", "-b", "main")
    git(project, "add", ".")
    git(project, "commit", "-m", "Initial probe")
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "-u", "origin", "main")
    assert run_installer(project, env, answers="y\ny\ny\ny\n").returncode == 0
    executable = project / ".venv/bin/chopper"
    executable.write_text('#!/bin/sh\nexec "$TEST_PYTHON" "$(dirname "$0")/../../probe.py"\n')
    executable.chmod(0o755)
    command = Path(env["HOME"]) / ".local/bin/chopper"
    menu = Path(env["XDG_DATA_HOME"]) / "applications/chopper.desktop"
    shortcut = desktop / "chopper.desktop"
    artifacts = [project / "chopper", command, menu, shortcut, project / ".chopper-install.json"]
    snapshot = [
        (path.lstat().st_ino, os.readlink(path) if path.is_symlink() else path.read_bytes())
        for path in artifacts
    ]
    gio = shutil.which("gio")
    assert gio is not None, "GLib is required for the menu/Desktop update recipe"
    probe_env = {
        **env,
        "GIO_USE_VFS": "local",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-chopper-test-bus",
    }

    def run_probes(expected):
        for args in ([str(command)], [gio, "launch", str(menu)], [gio, "launch", str(shortcut)]):
            output.unlink(missing_ok=True)
            subprocess.run(args, cwd=tmp_path, env=probe_env, check=True, capture_output=True, timeout=10)
            deadline = time.monotonic() + 3
            while not output.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert output.read_text() == expected

    run_probes("version-one")
    author = tmp_path / "author"
    git(tmp_path, "clone", "-b", "main", str(remote), str(author))
    (author / "probe.py").write_text(code.read_text().replace("version-one", "version-two"))
    git(author, "add", "probe.py")
    git(author, "commit", "-m", "Code-only update")
    git(author, "push", "origin", "main")
    Path(env["UV_CALLS"]).write_text("")
    git(project, "pull", "--ff-only")
    run_probes("version-two")
    assert snapshot == [
        (path.lstat().st_ino, os.readlink(path) if path.is_symlink() else path.read_bytes())
        for path in artifacts
    ]
    assert Path(env["UV_CALLS"]).read_text() == ""
