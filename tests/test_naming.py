from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from chopper.core.models import Candidate, CandidateType, Track
from chopper.core.naming import build_filename, unique_path

_DEFAULT_TRACK = Track(
    path=Path("/library/Burial/Untrue/03 - Etched Headplate.mp3"),
    artist="Burial",
    album="Untrue",
    title="Etched Headplate",
    track_number=3,
    duration_seconds=240.0,
    sample_rate=44100,
)


def _track(**overrides) -> Track:
    return replace(_DEFAULT_TRACK, **overrides)


def test_loop_filename_matches_spec_example():
    track = _track()
    candidate = Candidate(
        type=CandidateType.LOOP,
        start_seconds=72.0,
        end_seconds=72.0 + 4 * 60 / 139,
        score=0.9,
        bpm=139,
        bars=1,
    )
    assert build_filename(track, candidate) == "Burial_Untrue_03_loop_139bpm_1bars_01m12s.wav"


def test_half_bar_filename_has_no_slash_or_integer_truncation():
    candidate = Candidate(CandidateType.LOOP, 72.0, 73.0, 1.0, bpm=120, bars=0.5)
    assert build_filename(_track(), candidate) == "Burial_Untrue_03_loop_120bpm_0.5bars_01m12s.wav"


def test_quarter_bar_filename():
    candidate = Candidate(CandidateType.LOOP, 72, 72.5, 1, bpm=120, bars=0.25)
    assert build_filename(_track(), candidate) == "Burial_Untrue_03_loop_120bpm_0.25bars_01m12s.wav"


@pytest.mark.parametrize("bars", [3, 8, None, True, float("nan")])
def test_naming_refuses_unsupported_loop_lengths(bars):
    with pytest.raises(ValueError):
        build_filename(_track(), Candidate(CandidateType.LOOP, 0, 1, 1, bpm=120, bars=bars))


@pytest.mark.parametrize(
    "bars, end, expected",
    [
        (2, 76.0, "Burial_Untrue_03_loop_120bpm_2bars_01m12s.wav"),
        (4, 80.0, "Burial_Untrue_03_loop_120bpm_4bars_01m12s.wav"),
    ],
)
def test_manual_long_loop_filename(bars, end, expected):
    candidate = Candidate(CandidateType.LOOP, 72.0, end, 1.0, bpm=120, bars=bars)
    assert build_filename(_track(), candidate) == expected


@pytest.mark.parametrize("bars, end", [(2.0, 6.0), (4.0, 10.0)])
@pytest.mark.parametrize("file_format", ["wav", "flac"])
def test_manual_long_loop_export_preserves_original_audio(tmp_path, bars, end, file_format):
    from chopper.core.audio_io import export_candidates, load

    samples = np.column_stack([np.linspace(-0.5, 0.5, 12000), np.linspace(0.3, -0.3, 12000)]).astype(
        np.float32
    )
    before = samples.copy()
    candidate = Candidate(CandidateType.LOOP, 2.0, end, 1.0, bpm=120, bars=bars)
    paths = export_candidates(
        samples,
        1000,
        _track(sample_rate=1000, duration_seconds=12.0),
        [candidate],
        tmp_path,
        file_format=file_format,
    )
    assert len(paths) == 1 and f"_{bars:g}bars_" in paths[0].name
    exported, rate = load(paths[0], mono=False)
    assert rate == 1000 and exported.shape == (round((end - 2.0) * 1000), 2)
    np.testing.assert_allclose(exported, samples[2000 : round(end * 1000)], rtol=0, atol=2e-7)
    np.testing.assert_array_equal(samples, before)


def test_one_shot_filename_matches_spec_example():
    track = _track()
    candidate = Candidate(
        type=CandidateType.ONE_SHOT,
        start_seconds=72.340,
        end_seconds=72.9,
        score=0.8,
    )
    assert build_filename(track, candidate) == "Burial_Untrue_03_shot_01m12s340.wav"


def test_forbidden_characters_are_cleaned():
    track = _track(artist="AC/DC", album='Live: "1992"')
    candidate = Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.5, score=0.5)
    name = build_filename(track, candidate)
    assert "/" not in name
    assert '"' not in name
    assert ":" not in name


def test_unicode_characters_are_preserved_not_mangled():
    track = _track(artist="Björk", album="東京の夜 🎵", title="Jóga")
    candidate = Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.5, score=0.5)

    name = build_filename(track, candidate, extension="wav")

    assert "Björk" in name
    assert "東京の夜 🎵" in name


def test_sanitize_falls_back_to_placeholder_for_blank_names():
    track = _track(artist="   ", album="Untrue")  # espaces uniquement : vide après nettoyage
    candidate = Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.5, score=0.5)

    name = build_filename(track, candidate)

    assert "sans_nom" in name
    assert "  " not in name


def test_unicode_filename_can_actually_be_written_to_disk(tmp_path):
    """Le nom de fichier construit doit être utilisable tel quel par le
    système de fichiers, pas seulement correct en tant que chaîne."""
    track = _track(artist="Sigur Rós", album="Ágætis byrjun", track_number=None, title="Svefn-g-englar")
    candidate = Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.5, score=0.5)

    name = build_filename(track, candidate)
    path = tmp_path / name
    path.write_bytes(b"contenu")

    assert path.read_bytes() == b"contenu"


def test_unique_path_avoids_overwrite(tmp_path):
    (tmp_path / "sample.wav").touch()
    result = unique_path(tmp_path, "sample.wav")
    assert result == tmp_path / "sample_2.wav"

    (tmp_path / "sample_2.wav").touch()
    result = unique_path(tmp_path, "sample.wav")
    assert result == tmp_path / "sample_3.wav"


def test_unique_path_returns_original_when_free(tmp_path):
    result = unique_path(tmp_path, "sample.wav")
    assert result == tmp_path / "sample.wav"


def test_unique_path_skips_dangling_symlinks_without_touching_targets(tmp_path):
    target = tmp_path / "missing-source.wav"
    (tmp_path / "sample.wav").symlink_to(target)
    (tmp_path / "sample_2.wav").symlink_to(target)
    assert unique_path(tmp_path, "sample.wav") == tmp_path / "sample_3.wav"
    assert (tmp_path / "sample.wav").is_symlink()
    assert (tmp_path / "sample_2.wav").is_symlink()
    assert not target.exists()
