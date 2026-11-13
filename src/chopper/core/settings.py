from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import tomli_w
from platformdirs import user_cache_dir, user_config_dir

from chopper.core.models import AUTO_LOOP_LENGTHS_BARS, is_loop_length

APP_NAME = "chopper"
_DEFAULT_LOOP_LENGTHS_BARS = AUTO_LOOP_LENGTHS_BARS


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

    def __post_init__(self) -> None:
        count = self.candidates_per_track
        self.candidates_per_track = max(1, min(8, count)) if type(count) is int else 8
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
        return {k: v for k, v in data.items() if v is not None}

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


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or default_settings_path()
    content = tomli_w.dumps(settings.to_dict())
    path.parent.mkdir(parents=True, exist_ok=True)
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
