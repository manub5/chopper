from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from fcntl import LOCK_EX, flock
from pathlib import Path
from tempfile import NamedTemporaryFile

import tomli_w
from platformdirs import user_cache_dir, user_config_dir

from chopper.core.models import AUTO_LOOP_LENGTHS_BARS, is_loop_length

APP_NAME = "chopper"
_DEFAULT_LOOP_LENGTHS_BARS = AUTO_LOOP_LENGTHS_BARS


MAX_SAMPLES_PER_CATEGORY = 64


@dataclass
class Settings:
    library_root: str | None = None
    export_dir: str | None = None
    export_format: str = "wav"  # "wav" (24 bits, défaut) ou "flac"
    loop_lengths_bars: tuple[float, ...] = _DEFAULT_LOOP_LENGTHS_BARS
    loop_lengths_version: int = 3
    candidates_per_track: int = 8
    max_one_shot_seconds: float = 2.0
    gpu_mode: str = "auto"  # "auto" ou "cpu"
    auto_play: bool = True
    force_dark: bool = False
    dialog_locations: dict[str, str] = field(default_factory=dict)

    def dialog_start(self, purpose: str) -> str:
        value = self.dialog_locations.get(purpose)
        try:
            if (
                value
                and Path(value).is_absolute()
                and Path(value).is_dir()
                and os.access(value, os.R_OK | os.X_OK)
            ):
                return value
        except (OSError, ValueError):
            pass
        return ""

    def remember_dialog(self, purpose: str, directory: Path) -> None:
        self.dialog_locations = {**self.dialog_locations, purpose: str(directory.absolute())}

    def __post_init__(self) -> None:
        self.dialog_locations = (
            {
                k: v
                for k, v in self.dialog_locations.items()
                if k in {"library", "album", "track", "export"} and isinstance(v, str)
            }
            if isinstance(self.dialog_locations, dict)
            else {}
        )
        count = self.candidates_per_track
        self.candidates_per_track = max(1, min(MAX_SAMPLES_PER_CATEGORY, count)) if type(count) is int else 8
        values = self.loop_lengths_bars
        if isinstance(values, (tuple, list)):
            valid = {float(value) for value in values if is_loop_length(value)}
            self.loop_lengths_bars = tuple(value for value in AUTO_LOOP_LENGTHS_BARS if value in valid)
        else:
            self.loop_lengths_bars = ()
        if not self.loop_lengths_bars:
            self.loop_lengths_bars = AUTO_LOOP_LENGTHS_BARS

    def to_dict(self) -> dict:
        data = asdict(self)
        data["loop_lengths_bars"] = list(self.loop_lengths_bars)
        return {k: v for k, v in data.items() if v is not None and (k != "dialog_locations" or v)}

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        merged = {**cls().to_dict(), **data}
        version = data.get("loop_lengths_version")
        if type(version) is not int or version < 3:
            merged["loop_lengths_bars"] = AUTO_LOOP_LENGTHS_BARS
            merged["loop_lengths_version"] = 3
        return cls(**merged)


def default_settings_path() -> Path:
    return Path(user_config_dir(APP_NAME)) / "settings.toml"


def default_cache_path() -> Path:
    return Path(user_cache_dir(APP_NAME)) / "analyses.sqlite"


def _legacy_settings_path() -> Path:
    return Path(user_config_dir("choppeur")) / "settings.toml"


def load_settings(path: Path | None = None) -> Settings:
    if path is None:
        path = default_settings_path()
        if not path.exists() and not path.is_symlink():
            path = _legacy_settings_path()
    if not path.exists() and not path.is_symlink():
        return Settings()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Settings.from_dict(data)


def save_settings(settings: Settings, path: Path | None = None, *, previous: Settings | None = None) -> None:
    """Save atomically, merging edits against the current file if given a snapshot."""
    if previous is not None and previous == settings:
        return
    destination = path if path is not None else default_settings_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Lock a stable inode: replacing the TOML itself would invalidate its lock.
    with destination.with_name(f".{destination.name}.lock").open("ab") as lock:
        flock(lock, LOCK_EX)
        if previous is not None:
            old, new = asdict(previous), asdict(settings)
            if (
                destination.exists()
                or destination.is_symlink()
                or (path is None and _legacy_settings_path().is_file())
            ):
                current = asdict(load_settings(path))
                old_locations = old.pop("dialog_locations")
                new_locations = new.pop("dialog_locations")
                current.update({key: value for key, value in new.items() if value != old[key]})
                for key in old_locations.keys() | new_locations.keys():
                    if old_locations.get(key) != new_locations.get(key):
                        if key in new_locations:
                            current["dialog_locations"][key] = new_locations[key]
                        else:
                            current["dialog_locations"].pop(key, None)
                settings = Settings(**current)
        _write_settings(settings, destination)


def _write_settings(settings: Settings, path: Path) -> None:
    content = tomli_w.dumps(settings.to_dict())
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
