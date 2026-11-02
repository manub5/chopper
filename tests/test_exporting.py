from hashlib import sha256

import numpy as np
import pytest
import soundfile as sf

from chopper.core import audio_io
from chopper.core.models import Candidate, CandidateType


@pytest.fixture
def stereo_source(tmp_path):
    rate = 44100
    t = np.arange(rate * 2) / rate
    samples = np.column_stack([0.4 * np.sin(440 * 2 * np.pi * t), 0.2 * np.cos(220 * 2 * np.pi * t)])
    source = tmp_path / "source.flac"
    sf.write(source, samples, rate, subtype="PCM_24")
    samples, rate = audio_io.load(source, mono=False)
    track = audio_io.read_track(source)
    candidates = (
        Candidate(CandidateType.ONE_SHOT, 0.1, 0.5, 1),
        Candidate(CandidateType.LOOP, 0.5, 1.0, 1, bpm=120, bars=0.25),
    )
    return samples, rate, track, candidates


@pytest.mark.parametrize("file_format", ["wav", "flac"])
def test_buttons_export_stereo_to_root_in_selected_format(stereo_source, tmp_path, file_format):
    from chopper.core.exporting import export_batch

    samples, rate, track, candidates = stereo_source
    source_hash = sha256(track.path.read_bytes()).hexdigest()
    destination = tmp_path / "exports"
    report = export_batch(samples, rate, track, candidates, destination, file_format)
    assert report.error is None
    assert len(report.paths) == 2
    assert all(path.parent == destination and path.suffix == f".{file_format}" for path in report.paths)
    assert not (destination / "glissés").exists()
    info = sf.info(report.paths[0])
    assert (info.samplerate, info.channels, info.subtype) == (44100, 2, "PCM_24")
    data, exported_rate = sf.read(report.paths[0], dtype="float32")
    assert exported_rate == rate
    np.testing.assert_allclose(data, samples[4410:22050], atol=2 / 2**24)
    assert sha256(track.path.read_bytes()).hexdigest() == source_hash


def test_repeated_drags_create_distinct_permanent_wavs_in_unicode_subfolder(stereo_source, tmp_path):
    from chopper.core.exporting import export_drag

    samples, rate, track, candidates = stereo_source
    destination = tmp_path / "exports"
    first = export_drag(samples, rate, track, candidates[0], destination)
    before = first.read_bytes()
    second = export_drag(samples, rate, track, candidates[0], destination)
    assert first != second
    assert first.parent == second.parent == destination / "glissés"
    assert first.read_bytes() == before
    assert len(list(destination.glob("*.wav"))) == 0
    assert len(list((destination / "glissés").glob("*.wav"))) == 2
    info = sf.info(second)
    assert (info.format, info.subtype, info.samplerate, info.channels) == ("WAV", "PCM_24", 44100, 2)


def test_batch_collision_with_broken_link_does_not_retry_same_name_forever(stereo_source, tmp_path):
    from chopper.core.exporting import export_batch
    from chopper.core.naming import build_filename

    samples, rate, track, candidates = stereo_source
    destination = tmp_path / "exports"
    destination.mkdir()
    blocked = destination / build_filename(track, candidates[0])
    blocked.symlink_to(tmp_path / "absent.wav")
    report = export_batch(samples, rate, track, candidates[:1], destination, "wav")
    assert report.error is None
    assert len(report.paths) == 1 and report.paths[0] != blocked
    assert report.paths[0].is_file() and blocked.is_symlink()


def test_disk_full_keeps_first_success_and_cleans_partial_second(stereo_source, tmp_path, monkeypatch):
    from chopper.core.exporting import export_batch

    samples, rate, track, candidates = stereo_source
    real_write = sf.write
    written = []

    def fail_second(file, data, samplerate, **kwargs):
        written.append(file)
        if len(written) == 2:
            from pathlib import Path

            Path(file).write_bytes(b"partial")
            raise OSError("No space left on device")
        return real_write(file, data, samplerate, **kwargs)

    monkeypatch.setattr(sf, "write", fail_second)
    report = export_batch(samples, rate, track, candidates, tmp_path / "exports", "wav")
    assert len(report.paths) == 1
    assert report.paths[0].is_file()
    assert report.paths[0].name in written[0]
    assert "No space left" in report.error
    from pathlib import Path

    assert not Path(written[1]).exists()
    assert tuple((tmp_path / "exports").iterdir()) == report.paths


def test_unavailable_network_folder_reports_failure_without_success(stereo_source, tmp_path, monkeypatch):
    from pathlib import Path

    from chopper.core.exporting import export_batch

    samples, rate, track, candidates = stereo_source
    destination = tmp_path / "nas"
    real_mkdir = Path.mkdir

    def disconnected(self, *args, **kwargs):
        if self == destination:
            raise OSError("Stale file handle")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", disconnected)
    report = export_batch(samples, rate, track, candidates, destination, "wav")
    assert report.paths == ()
    assert "Stale file handle" in report.error
    assert not destination.exists()


def test_file_in_place_of_destination_reports_error_without_collision_loop(
    stereo_source, tmp_path, monkeypatch
):
    from chopper.core.exporting import export_batch

    samples, rate, track, candidates = stereo_source
    destination = tmp_path / "not-a-directory"
    destination.write_bytes(b"keep this file")
    real_segment = audio_io.export_segment
    attempts = []

    def bounded_segment(*args, **kwargs):
        attempts.append(True)
        if len(attempts) >= 3:
            raise RuntimeError("collision retry loop detected")
        return real_segment(*args, **kwargs)

    monkeypatch.setattr(audio_io, "export_segment", bounded_segment)
    report = export_batch(samples, rate, track, candidates, destination, "wav")
    assert len(attempts) <= 1
    assert report.paths == () and report.error
    assert destination.read_bytes() == b"keep this file"


@pytest.mark.parametrize("file_format", ["mp3", "wav/../../outside", ""])
def test_invalid_format_writes_nothing(stereo_source, tmp_path, file_format):
    from chopper.core.exporting import export_batch

    samples, rate, track, candidates = stereo_source
    destination = tmp_path / "exports"
    report = export_batch(samples, rate, track, candidates, destination, file_format)
    assert report.paths == () and report.error
    assert not destination.exists()


def test_empty_batch_creates_no_directory(stereo_source, tmp_path):
    from chopper.core.exporting import export_batch

    samples, rate, track, _candidates = stereo_source
    destination = tmp_path / "exports"
    report = export_batch(samples, rate, track, (), destination, "wav")
    assert report.paths == () and report.error is None
    assert not destination.exists()


def test_drag_and_player_receive_identical_stereo_excerpt(qapp, stereo_source, tmp_path, monkeypatch):
    from types import SimpleNamespace

    import sounddevice as sd

    from chopper.core.exporting import export_drag
    from chopper.gui.preview_player import PreviewPlayer

    samples, rate, track, candidates = stereo_source
    received = []
    monkeypatch.setattr(sd, "play", lambda data, samplerate, **kwargs: received.append(data.copy()))
    monkeypatch.setattr(sd, "get_stream", lambda: SimpleNamespace(active=True))
    monkeypatch.setattr(sd, "stop", lambda **kwargs: None)
    player = PreviewPlayer()
    try:
        player.play(samples, rate, candidates[0], 1)
        path = export_drag(samples, rate, track, candidates[0], tmp_path / "exports")
        exported, _rate = sf.read(path, dtype="float32")
        np.testing.assert_allclose(exported, received[0], atol=2 / 2**24)
    finally:
        player.stop()
