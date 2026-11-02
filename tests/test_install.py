import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def installer_sandbox(tmp_path):
    project = tmp_path / "project with spaces"
    project.mkdir()
    shutil.copyfile(Path(__file__).parents[1] / "install.sh", project / "install.sh")
    tools = tmp_path / "tools"
    tools.mkdir()
    for name, content in {
        "uv": '#!/usr/bin/env bash\nprintf "%s\\n" "$PWD" "$@" >> "$UV_CALLS"\n',
        "uname": '#!/usr/bin/env bash\nprintf "Linux\\n"\n',
        "dpkg": "#!/usr/bin/env bash\nexit 0\n",
        "apt-get": "#!/usr/bin/env bash\nexit 91\n",
        "sudo": "#!/usr/bin/env bash\nexit 92\n",
        "curl": "#!/usr/bin/env bash\nexit 93\n",
    }.items():
        script = tools / name
        script.write_text(content)
        script.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "PATH": f"{tools}:/usr/bin:/bin",
        "HOME": str(home),
        "UV_CALLS": str(tmp_path / "uv-calls"),
    }
    old = project / "choppeur"
    old.write_text("old launcher sentinel")
    return project, env


def test_installer_generates_chopper_and_launcher_preserves_arguments(installer_sandbox, tmp_path):
    project, env = installer_sandbox
    result = subprocess.run(
        ["bash", str(project / "install.sh")],
        check=False,
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    launcher = project / "chopper"
    assert launcher.is_file() and os.access(launcher, os.X_OK)
    assert (project / "choppeur").read_text() == "old launcher sentinel"
    Path(env["UV_CALLS"]).write_text("")
    subprocess.run(
        [str(launcher), "--test", "argument with spaces"],
        env=env,
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert Path(env["UV_CALLS"]).read_text().splitlines() == [
        str(project),
        "run",
        "chopper",
        "--test",
        "argument with spaces",
    ]
    # Re-running an installation must safely update its own generated launcher.
    subprocess.run(
        ["bash", str(project / "install.sh")],
        env=env,
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert (project / "choppeur").read_text() == "old launcher sentinel"


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_installer_refuses_to_overwrite_unrelated_launcher(installer_sandbox, tmp_path, kind):
    project, env = installer_sandbox
    target = tmp_path / "user-script"
    target.write_text("keep this unrelated file")
    launcher = project / "chopper"
    if kind == "symlink":
        launcher.symlink_to(target)
    else:
        launcher.write_bytes(target.read_bytes())
    result = subprocess.run(
        ["bash", str(project / "install.sh")],
        check=False,
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "refusing" in (result.stderr + result.stdout).lower()
    assert launcher.read_text() == target.read_text() == "keep this unrelated file"
