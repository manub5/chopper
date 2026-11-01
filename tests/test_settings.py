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
    assert settings.loop_lengths_bars == (0.25, 0.5, 1.0)
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
        ([2, 4, 8], (0.25, 0.5, 1.0)),
        ([1, 2, 4, 8], (1.0,)),
        ([0.5, 1, 0.5, 8], (0.5, 1.0)),
        ([True, "1/2", None, -1], (0.25, 0.5, 1.0)),
        ([], (0.25, 0.5, 1.0)),
        (None, (0.25, 0.5, 1.0)),
    ],
)
def test_old_lengths_migrate_idempotently(old, expected, tmp_path):
    settings = Settings.from_dict({"loop_lengths_bars": old, "loop_lengths_version": 3})
    assert settings.loop_lengths_bars == expected
    path = tmp_path / "settings.toml"
    save_settings(settings, path)
    assert load_settings(path).loop_lengths_bars == expected
    assert Settings.from_dict(settings.to_dict()).to_dict() == settings.to_dict()


@pytest.mark.parametrize("version", [None, 1, "invalid", True])
def test_legacy_single_length_reactivates_all_once_without_rewriting(version, tmp_path):
    data = {"loop_lengths_bars": [1.0], "auto_play": False, "force_dark": True}
    if version is not None:
        data["loop_lengths_version"] = version
    loaded = Settings.from_dict(data)
    assert loaded.loop_lengths_bars == (0.25, 0.5, 1.0)
    assert loaded.loop_lengths_version == 3
    assert not loaded.auto_play and loaded.force_dark
    loaded.loop_lengths_bars = (1.0,)
    path = tmp_path / "settings.toml"
    save_settings(loaded, path)
    assert load_settings(path).loop_lengths_bars == (1.0,)
    assert load_settings(path).loop_lengths_version == 3


def test_loading_legacy_file_is_read_only_and_migration_is_stable(tmp_path):
    path = tmp_path / "settings.toml"
    before = "loop_lengths_bars = [1.0]\ncandidates_per_track = 50\n"
    path.write_text(before)
    migrated = load_settings(path)
    assert path.read_text() == before
    assert migrated.loop_lengths_bars == (0.25, 0.5, 1.0)
    assert migrated.candidates_per_track == 8
    assert Settings.from_dict(migrated.to_dict()) == migrated


@pytest.mark.parametrize(
    "lengths",
    [
        (0.25,),
        (0.5,),
        (1.0,),
        (0.25, 0.5),
        (0.25, 1.0),
        (0.5, 1.0),
        (0.25, 0.5, 1.0),
    ],
)
@pytest.mark.parametrize("version", [None, 1, 2, "invalid", True])
def test_v2_lengths_restore_all_once(lengths, version, tmp_path):
    data = {
        "loop_lengths_bars": list(lengths),
        "auto_play": False,
        "force_dark": True,
        "export_dir": str(tmp_path / "custom"),
    }
    if version is not None:
        data["loop_lengths_version"] = version
    migrated = Settings.from_dict(data)
    assert migrated.loop_lengths_bars == (0.25, 0.5, 1.0)
    assert migrated.loop_lengths_version == 3
    assert not migrated.auto_play and migrated.force_dark
    assert migrated.export_dir == str(tmp_path / "custom")
    migrated.loop_lengths_bars = lengths
    path = tmp_path / "settings.toml"
    save_settings(migrated, path)
    for _ in range(2):
        loaded = load_settings(path)
        assert loaded.loop_lengths_bars == lengths
        assert loaded.loop_lengths_version == 3
        save_settings(loaded, path)


@pytest.mark.parametrize("value, expected", [(0, 1), (-10, 1), (3, 3), (50, 8)])
def test_category_count_is_bounded(value, expected):
    assert Settings(candidates_per_track=value).candidates_per_track == expected


@pytest.mark.parametrize("value", [None, True, "8", 2.5, float("inf"), float("nan")])
def test_invalid_category_count_falls_back_to_eight(value):
    assert Settings.from_dict({"candidates_per_track": value}).candidates_per_track == 8


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
