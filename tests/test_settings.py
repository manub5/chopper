import pytest

from choppeur.core.settings import (
    Settings,
    default_cache_path,
    default_settings_path,
    load_settings,
    save_settings,
)


def test_defaults():
    settings = Settings()
    assert settings.export_format == "wav"
    assert settings.loop_lengths_bars == (0.5, 1.0)
    assert settings.gpu_mode == "auto"


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "settings.toml"
    original = Settings(
        library_root="/musique",
        export_dir="/musique/export",
        export_format="flac",
        loop_lengths_bars=(0.5, 1.0),
        candidates_per_track=5,
        max_one_shot_seconds=1.5,
        gpu_mode="cpu",
    )

    save_settings(original, path)
    loaded = load_settings(path)

    assert loaded == original


@pytest.mark.parametrize(
    "old, expected",
    [
        ([2, 4, 8], (0.5, 1.0)),
        ([1, 2, 4, 8], (1.0,)),
        ([0.5, 1, 0.5, 8], (0.5, 1.0)),
        ([True, "1/2", None, -1], (0.5, 1.0)),
        ([], (0.5, 1.0)),
        (None, (0.5, 1.0)),
    ],
)
def test_old_lengths_migrate_idempotently(old, expected, tmp_path):
    settings = Settings.from_dict({"loop_lengths_bars": old})
    assert settings.loop_lengths_bars == expected
    path = tmp_path / "settings.toml"
    save_settings(settings, path)
    assert load_settings(path).loop_lengths_bars == expected
    assert Settings.from_dict(settings.to_dict()).to_dict() == settings.to_dict()


def test_load_missing_file_returns_defaults(tmp_path):
    loaded = load_settings(tmp_path / "does_not_exist.toml")
    assert loaded == Settings()


def test_default_paths_point_to_choppeur_directories():
    assert default_settings_path().name == "settings.toml"
    assert default_cache_path().name == "analyses.sqlite"
    assert "choppeur" in str(default_settings_path())
    assert "choppeur" in str(default_cache_path())


def test_load_partial_file_fills_in_defaults(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text('export_format = "flac"\n')

    loaded = load_settings(path)

    assert loaded.export_format == "flac"
    assert loaded.candidates_per_track == Settings().candidates_per_track


def test_old_settings_get_new_ui_defaults_without_rewriting_the_file(tmp_path):
    path = tmp_path / "settings.toml"
    original = 'export_format = "flac"\n'
    path.write_text(original)
    loaded = load_settings(path)
    assert loaded.auto_play is True
    assert loaded.force_dark is False
    assert loaded.export_format == "flac"
    assert path.read_text() == original


@pytest.mark.parametrize("auto_play", [False, True])
@pytest.mark.parametrize("force_dark", [False, True])
def test_ui_preferences_roundtrip_including_false_values(tmp_path, auto_play, force_dark):
    path = tmp_path / "settings.toml"
    original = Settings(auto_play=auto_play, force_dark=force_dark)
    save_settings(original, path)
    loaded = load_settings(path)
    assert loaded.auto_play is auto_play
    assert loaded.force_dark is force_dark
    assert loaded == original
