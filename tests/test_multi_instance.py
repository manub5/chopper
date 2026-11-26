import multiprocessing
from dataclasses import replace

import numpy as np
import soundfile as sf

from chopper.core.audio_io import read_track
from chopper.core.cache import AnalysisCache
from chopper.core.exporting import export_batch
from chopper.core.models import Analysis, Candidate, CandidateType
from chopper.core.settings import load_settings, save_settings


def _run_instance(root, index, barrier):
    preferences = root / "settings.toml"
    previous = load_settings(preferences)
    updated = replace(previous, **({"force_dark": True} if index else {"auto_play": False}))
    updated.remember_dialog("album" if index else "track", root / str(index))
    track = read_track(root / "Synth.wav")
    analysis = Analysis(track, 120.0, (0.0,), (0.0,))
    with AnalysisCache(root / "shared.sqlite") as cache:
        barrier.wait(timeout=15)
        save_settings(updated, preferences, previous=previous)
        cache.set(analysis)
        assert cache.get(track) == analysis
        barrier.wait(timeout=15)
        report = export_batch(
            np.full(8000, 0.25 if index else -0.25),
            8000,
            track,
            (Candidate(CandidateType.ONE_SHOT, 0, 0.25, 1),),
            root / "exports",
            "wav",
        )
        assert report.error is None and len(report.paths) == 1


def test_two_processes_preserve_preferences_cache_and_exports(tmp_path):
    source = tmp_path / "Synth.wav"
    sf.write(source, np.zeros(8000), 8000)
    original = source.read_bytes()
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    processes = [context.Process(target=_run_instance, args=(tmp_path, index, barrier)) for index in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=25)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    settings = load_settings(tmp_path / "settings.toml")
    assert settings.force_dark and not settings.auto_play
    assert settings.dialog_locations == {"track": str(tmp_path / "0"), "album": str(tmp_path / "1")}
    with AnalysisCache(tmp_path / "shared.sqlite") as cache:
        track = read_track(source)
        assert cache.get(track) == Analysis(track, 120.0, (0.0,), (0.0,))
    files = list((tmp_path / "exports").glob("*.wav"))
    assert len(files) == 2
    assert sorted(float(sf.read(path)[0].mean()) for path in files) == [-0.25, 0.25]
    assert source.read_bytes() == original
