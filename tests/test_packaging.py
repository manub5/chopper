import importlib
import tomllib
from pathlib import Path


def test_chopper_import_and_console_entry_points():
    app = importlib.import_module("chopper.app")
    assert callable(app.main)
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert metadata["project"]["name"] == "chopper"
    assert metadata["project"]["scripts"] == {
        "chopper": "chopper.app:main",
        "choppeur": "chopper.app:main",
    }
    assert metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/chopper"]
