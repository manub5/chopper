from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import QEventLoop, QTimer

from chopper.core.cache import AnalysisCache
from chopper.core.models import Analysis, Candidate, CandidateType, Track
from chopper.core.settings import Settings
from chopper.gui import workers

SAMPLE_RATE = 22050


def test_cached_track_worker_provides_all_four_categories(qapp, tmp_path):
    from collections import Counter

    path = tmp_path / "source.wav"
    samples = np.column_stack([np.full(18000, 0.25), np.full(18000, -0.5)]).astype(np.float32)
    sf.write(path, samples, 1000, subtype="FLOAT")
    before = path.read_bytes()
    track = workers.audio_io.read_track(path)
    analysis = Analysis(
        track, 120, (), tuple(float(t) for t in range(0, 18, 2)), tuple(float(t) + 0.1 for t in range(9))
    )
    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        cache.set(analysis)
        settings = Settings.from_dict({"loop_lengths_bars": [1.0]})
        worker = workers.TrackAnalysisWorker(track, settings, cache)
        results = []
        errors = []
        worker.finished.connect(results.append)
        worker.failed.connect(errors.append)
        worker.run()
    assert errors == []
    assert len(results) == 1
    assert Counter((c.type.value, c.bars) for c in results[0].candidates) == {
        ("loop", 1.0): 8,
        ("loop", 0.5): 8,
        ("loop", 0.25): 8,
        ("shot", None): 8,
    }
    np.testing.assert_array_equal(results[0].samples, samples)
    assert path.read_bytes() == before


def _write_click_track(path, n_clicks=6, interval_seconds=0.5, sample_rate=SAMPLE_RATE):
    total_samples = int((n_clicks * interval_seconds + 0.5) * sample_rate)
    signal = np.zeros(total_samples, dtype=np.float32)
    click_len = int(0.01 * sample_rate)
    rng = np.random.default_rng(0)
    for i in range(n_clicks):
        start = int(i * interval_seconds * sample_rate)
        signal[start : start + click_len] += rng.uniform(-1.0, 1.0, click_len)
    sf.write(str(path), signal, sample_rate, subtype="PCM_24")


def _track(path) -> Track:
    return Track(
        path=path,
        artist="Burial",
        album="Untrue",
        title="Etched Headplate",
        track_number=3,
        duration_seconds=3.5,
        sample_rate=SAMPLE_RATE,
    )


def _fake_analyze_rhythm(path, *, device):
    return 120.0, (0.0, 0.5, 1.0, 1.5, 2.0, 2.5), (0.0, 2.0)


def test_analyze_track_returns_candidates_and_fills_cache(tmp_path, monkeypatch):
    audio_path = tmp_path / "track.wav"
    _write_click_track(audio_path)
    track = _track(audio_path)
    monkeypatch.setattr(workers.rhythm, "analyze_rhythm", _fake_analyze_rhythm)

    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        assert cache.get(track) is None

        analysis, candidates = workers.analyze_track(track, Settings(), cache)

        assert analysis.tempo_bpm == 120.0
        assert len(candidates) > 0
        assert cache.get(track) == analysis


def test_analyze_track_uses_cache_without_recomputing_rhythm(tmp_path, monkeypatch):
    audio_path = tmp_path / "track.wav"
    _write_click_track(audio_path)
    track = _track(audio_path)
    monkeypatch.setattr(workers.rhythm, "analyze_rhythm", _fake_analyze_rhythm)

    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        workers.analyze_track(track, Settings(), cache)

        def _boom(*args, **kwargs):
            raise AssertionError("analyze_rhythm ne doit pas être rappelé : le cache doit suffire")

        monkeypatch.setattr(workers.rhythm, "analyze_rhythm", _boom)

        analysis, candidates = workers.analyze_track(track, Settings(), cache)
        assert analysis.tempo_bpm == 120.0
        assert len(candidates) > 0


@pytest.mark.parametrize("use_cached_analysis", [False, True])
@pytest.mark.parametrize(
    ("downbeats", "expected_starts"),
    [((0.5, 2.5, 4.5), {0.5, 2.5}), ((), set())],
)
def test_loop_starts_follow_tracker_downbeats_not_all_beats(
    tmp_path, monkeypatch, use_cached_analysis, downbeats, expected_starts
):
    audio_path = tmp_path / "track.wav"
    _write_click_track(audio_path, n_clicks=11)
    track = _track(audio_path)

    class FakeTracker:
        def __call__(self, path):
            return np.arange(0.0, 6.0, 0.5), np.asarray(downbeats)

    # Replace only model inference; keep rhythm conversion and candidate selection real.
    monkeypatch.setattr(workers.rhythm, "_get_tracker", lambda checkpoint, device: FakeTracker())
    settings = Settings(loop_lengths_bars=(1,), candidates_per_track=20, gpu_mode="cpu")

    with AnalysisCache(tmp_path / "cache.sqlite") as cache:
        if use_cached_analysis:
            workers.analyze_track(track, settings, cache)

            def unexpected_inference(checkpoint, device):
                raise AssertionError("Cached analysis must not run model inference")

            monkeypatch.setattr(workers.rhythm, "_get_tracker", unexpected_inference)

        analysis, candidates = workers.analyze_track(track, settings, cache)

    loops = [candidate for candidate in candidates if candidate.type is CandidateType.LOOP]
    assert {candidate.start_seconds for candidate in loops} == expected_starts
    assert analysis.downbeat_times == downbeats


def test_track_analysis_worker_emits_finished(monkeypatch, tmp_path):
    track = _track(tmp_path / "track.wav")
    _write_click_track(track.path)
    fake_analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
    fake_candidates = [Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.2, score=1.0)]
    monkeypatch.setattr(workers, "analyze_track", lambda *a, **k: (fake_analysis, fake_candidates))

    worker = workers.TrackAnalysisWorker(track, Settings())
    received = []
    worker.finished.connect(received.append)

    worker.run()

    assert received[0].analysis == fake_analysis
    assert received[0].candidates == tuple(fake_candidates)


def test_track_analysis_worker_emits_failed_on_error(monkeypatch, tmp_path):
    track = _track(tmp_path / "track.wav")

    def _boom(*args, **kwargs):
        raise RuntimeError("échec de décodage")

    monkeypatch.setattr(workers, "analyze_track", _boom)

    worker = workers.TrackAnalysisWorker(track, Settings())
    received = []
    worker.failed.connect(received.append)

    worker.run()

    assert received == ["échec de décodage"]


def test_album_analysis_worker_processes_all_tracks_with_progress(monkeypatch, tmp_path):
    tracks = [_track(tmp_path / f"track{i}.wav") for i in range(3)]
    monkeypatch.setattr(workers, "tracks_in_folder", lambda folder: tracks)

    def _fake_analyze(track, settings, cache=None):
        analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
        return analysis, []

    monkeypatch.setattr(workers, "analyze_track", _fake_analyze)

    worker = workers.AlbumAnalysisWorker(tmp_path, Settings())
    scan_events = []
    progress_events = []
    done_events = []
    finished_events = []
    worker.scan_done.connect(scan_events.append)
    worker.progress.connect(lambda done, total: progress_events.append((done, total)))
    worker.track_done.connect(lambda analysis, candidates: done_events.append(analysis))
    worker.finished.connect(lambda: finished_events.append(True))

    worker.run()

    assert scan_events == [3]
    assert progress_events == [(1, 3), (2, 3), (3, 3)]
    assert len(done_events) == 3
    assert finished_events == [True]


def test_album_analysis_worker_continues_after_one_track_fails(monkeypatch, tmp_path):
    tracks = [_track(tmp_path / f"track{i}.wav") for i in range(3)]
    monkeypatch.setattr(workers, "tracks_in_folder", lambda folder: tracks)

    def _fake_analyze(track, settings, cache=None):
        if track.path.name == "track1.wav":
            raise RuntimeError("piste corrompue")
        return Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=()), []

    monkeypatch.setattr(workers, "analyze_track", _fake_analyze)

    worker = workers.AlbumAnalysisWorker(tmp_path, Settings())
    failed_events = []
    done_events = []
    worker.track_failed.connect(lambda track, message: failed_events.append((track, message)))
    worker.track_done.connect(lambda analysis, candidates: done_events.append(analysis))

    worker.run()

    assert len(failed_events) == 1
    assert failed_events[0][1] == "piste corrompue"
    assert len(done_events) == 2


def test_album_analysis_survives_a_network_share_disconnecting_mid_analysis(monkeypatch, tmp_path):
    """
    Edge case explicitement demandé : un chemin réseau (NAS) qui se
    déconnecte pendant l'analyse d'un album. Les pistes déjà traitées avant
    la coupure doivent rester acquises, et chaque piste après la coupure doit
    échouer proprement (track_failed) sans jamais interrompre la boucle -
    jusqu'à la fin de l'album, même si le montage ne revient jamais.
    """
    tracks = [_track(tmp_path / f"track{i}.wav") for i in range(5)]
    monkeypatch.setattr(workers, "tracks_in_folder", lambda folder: tracks)

    # Le montage réseau "tombe" après la 2e piste et ne revient jamais.
    def _fake_analyze(track, settings, cache=None):
        index = int(track.path.stem.removeprefix("track"))
        if index >= 2:
            raise OSError(
                "[Errno 116] Stale file handle: " + str(track.path)
            )  # ESTALE typique d'un montage NFS/CIFS perdu en cours de route
        return Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=()), []

    monkeypatch.setattr(workers, "analyze_track", _fake_analyze)

    worker = workers.AlbumAnalysisWorker(tmp_path, Settings())
    done_events = []
    failed_events = []
    finished_events = []
    worker.track_done.connect(lambda analysis, candidates: done_events.append(analysis))
    worker.track_failed.connect(lambda track, message: failed_events.append((track, message)))
    worker.finished.connect(lambda: finished_events.append(True))

    worker.run()  # ne doit jamais lever, même avec 3 échecs réseau d'affilée

    assert len(done_events) == 2  # track0, track1 : acquises avant la coupure
    assert len(failed_events) == 3  # track2, track3, track4 : toutes tentées malgré la panne
    assert all("Stale file handle" in message for _, message in failed_events)
    assert finished_events == [True]


def test_album_analysis_survives_folder_disconnecting_before_the_scan(monkeypatch, tmp_path):
    """
    Edge case explicitement demandé : un chemin réseau qui se déconnecte,
    cette fois avant même de pouvoir lister les pistes (dossier NAS démonté,
    ou simplement supprimé, juste avant de cliquer "Analyser l'album").
    Sans garde-fou, l'exception tuait run() avant finished.emit() : le
    bouton et la bibliothèque restaient désactivés pour toujours, sans
    aucun signal pour le signaler.
    """

    def _boom(folder):
        raise OSError("[Errno 5] Input/output error: " + str(folder))

    monkeypatch.setattr(workers, "tracks_in_folder", _boom)

    worker = workers.AlbumAnalysisWorker(tmp_path, Settings())
    scan_failed_events = []
    finished_events = []
    worker.scan_failed.connect(scan_failed_events.append)
    worker.finished.connect(lambda: finished_events.append(True))

    worker.run()  # ne doit jamais lever

    assert len(scan_failed_events) == 1
    assert "Input/output error" in scan_failed_events[0]
    assert finished_events == [True]  # indispensable : c'est ce qui débloque l'interface


def test_album_analysis_worker_stop_before_run_processes_nothing(monkeypatch, tmp_path):
    tracks = [_track(tmp_path / "track0.wav")]
    monkeypatch.setattr(workers, "tracks_in_folder", lambda folder: tracks)
    monkeypatch.setattr(
        workers,
        "analyze_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("ne doit pas être appelé")),
    )

    worker = workers.AlbumAnalysisWorker(tmp_path, Settings())
    worker.stop()
    finished_events = []
    worker.finished.connect(lambda: finished_events.append(True))

    worker.run()

    assert finished_events == [True]


def test_tracks_in_folder_reads_only_direct_children(tmp_path):
    import numpy as np
    import soundfile as sf

    (tmp_path / "01.wav").write_bytes(b"")
    sf.write(str(tmp_path / "02.wav"), np.zeros(10, dtype=np.float32), 44100)
    nested = tmp_path / "Nested"
    nested.mkdir()
    sf.write(str(nested / "03.wav"), np.zeros(10, dtype=np.float32), 44100)

    found = workers.tracks_in_folder(tmp_path)

    assert {t.path.name for t in found} == {"01.wav", "02.wav"}


def test_start_in_thread_runs_worker_to_completion(qapp, monkeypatch, tmp_path):
    track = _track(tmp_path / "track.wav")
    _write_click_track(track.path)
    fake_analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
    monkeypatch.setattr(workers, "analyze_track", lambda *a, **k: (fake_analysis, []))

    worker = workers.TrackAnalysisWorker(track, Settings())
    received = []
    worker.finished.connect(lambda result: received.append(result.analysis))

    thread = workers.start_in_thread(worker)

    # worker.finished est émis depuis le thread d'analyse ; le "quit" du thread
    # (connecté dans start_in_thread) est donc livré en connexion "queued" et a
    # besoin que la boucle d'évènements du thread principal tourne pour être
    # traité. On la fait tourner jusqu'à la fin de l'analyse (ou timeout).
    loop = QEventLoop()
    thread.finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    thread.start()
    loop.exec()

    assert received, "aucun résultat reçu"
    assert received == [fake_analysis]


def test_track_worker_returns_original_stereo_audio(monkeypatch, tmp_path):
    path = tmp_path / "stereo.wav"
    samples = np.column_stack([np.full(1000, 0.25), np.full(1000, -0.5)]).astype(np.float32)
    sf.write(path, samples, 1000, subtype="FLOAT")
    before = path.read_bytes()
    analysis = Analysis(workers.audio_io.read_track(path), 120.0, (), ())
    monkeypatch.setattr(workers, "analyze_track", lambda *args: (analysis, []))
    worker = workers.TrackAnalysisWorker(workers.audio_io.read_track(path), Settings())
    results = []
    worker.finished.connect(results.append)
    worker.run()
    assert len(results) == 1
    assert results[0].sample_rate == 1000
    np.testing.assert_array_equal(results[0].samples, samples)
    assert results[0].samples.shape == (1000, 2)
    assert path.read_bytes() == before


@pytest.fixture
def memory_track(loaded_track, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("In-memory search must not load, detect or access cache")

    for module, name in [
        (workers.audio_io, "load"),
        (workers.rhythm, "analyze_rhythm"),
        (workers.rhythm, "resolve_device"),
        (workers.onsets, "detect_onsets"),
        (AnalysisCache, "get"),
        (AnalysisCache, "set"),
        (workers, "analyze_track"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    samples = np.column_stack([np.full(18000, 0.25), np.full(18000, -0.5)]).astype(np.float32)
    samples.setflags(write=False)
    analysis = replace(
        loaded_track.analysis,
        track=replace(loaded_track.analysis.track, duration_seconds=18.0),
        downbeat_times=tuple(float(t) for t in range(0, 19, 2)),
        onset_times=tuple(float(t) + 0.1 for t in range(18)),
    )
    return replace(loaded_track, analysis=analysis, samples=samples)


@pytest.mark.parametrize("length", [0.25, 0.5, 1.0, 2.0, 4.0])
def test_memory_search_only_uses_selected_length_and_settings_limits(memory_track, length):
    before = memory_track.samples.copy()
    settings = Settings(candidates_per_track=2, max_one_shot_seconds=0.2)
    found, message = workers.search_candidates(memory_track, settings, window=(2.0, 18.0), length_bars=length)
    loops = [c for c in found if c.type is CandidateType.LOOP]
    shots = [c for c in found if c.type is CandidateType.ONE_SHOT]
    assert isinstance(found, tuple) and isinstance(message, str)
    assert len(loops) == len(shots) == 2
    assert {c.bars for c in loops} == {length}
    assert all(c.duration_seconds == pytest.approx(2 * length) for c in loops)
    assert all(c.duration_seconds <= 0.2 + 1e-12 for c in shots)
    assert all(2.0 <= c.start_seconds < c.end_seconds <= 18.0 for c in found)
    assert [c.score for c in found] == sorted((c.score for c in found), reverse=True)
    np.testing.assert_array_equal(memory_track.samples, before)
    assert len(memory_track.candidates) == 2


def test_whole_track_search_uses_automatic_settings_not_previous_manual_length(memory_track):
    settings = Settings(loop_lengths_bars=(0.25, 1.0), candidates_per_track=2, max_one_shot_seconds=0.2)
    workers.search_candidates(memory_track, settings, window=(2.0, 18.0), length_bars=4.0)
    found, _ = workers.search_candidates(memory_track, settings)
    loops = [c for c in found if c.type is CandidateType.LOOP]
    shots = [c for c in found if c.type is CandidateType.ONE_SHOT]
    assert len(found) == 6 and len(shots) == 2
    assert {c.bars for c in loops} == {0.25, 1.0}
    assert {c.bars: sum(other.bars == c.bars for other in loops) for c in loops} == {0.25: 2, 1.0: 2}
    assert settings.loop_lengths_bars == (0.25, 1.0)


def test_short_selection_still_finds_the_two_cached_onsets(loaded_track):
    loaded = replace(loaded_track, analysis=replace(loaded_track.analysis, onset_times=(0.1, 0.3)))
    found, message = workers.search_candidates(
        loaded, Settings(candidates_per_track=2, max_one_shot_seconds=0.2), window=(0.0, 0.6), length_bars=4.0
    )
    assert len(found) == 2 and all(c.type is CandidateType.ONE_SHOT for c in found)
    assert all(0.0 <= c.start_seconds < c.end_seconds <= 0.6 for c in found)
    assert "4-bar" in message and "2 one-shots" in message
    assert "too short" in message.lower()


@pytest.mark.parametrize("downbeats,tempo", [((), 120.0), ((0.0,), 120.0), ((0.0, 2.0), 0.0)])
def test_missing_usable_rhythm_explains_one_shots_without_claiming_too_short(memory_track, downbeats, tempo):
    loaded = replace(
        memory_track, analysis=replace(memory_track.analysis, downbeat_times=downbeats, tempo_bpm=tempo)
    )
    found, message = workers.search_candidates(
        loaded, Settings(candidates_per_track=2), window=(0.0, 0.6), length_bars=4.0
    )
    assert found and all(c.type is CandidateType.ONE_SHOT for c in found)
    assert "downbeat" in message.lower() and "one-shot" in message.lower()
    assert "too short" not in message.lower()


def test_empty_search_is_clear_without_inventing_short_selection(memory_track):
    loaded = replace(
        memory_track, analysis=replace(memory_track.analysis, downbeat_times=(0.0, 2.0), onset_times=())
    )
    found, message = workers.search_candidates(loaded, Settings(), window=(5.0, 15.0), length_bars=4.0)
    assert found == () and "no samples" in message.lower()
    assert "too short" not in message.lower()


@pytest.mark.parametrize(
    "window,length",
    [
        (None, 1.0),
        ((0.0, 2.0), None),
        ((0.0, 2.0), 3.0),
        ((0.0, 2.0), True),
        ((0.0, 2.0), float("nan")),
        ((2.0, 0.0), 1.0),
        ((-1.0, 2.0), 1.0),
    ],
)
def test_memory_search_rejects_inconsistent_request(memory_track, window, length):
    with pytest.raises(ValueError):
        workers.search_candidates(memory_track, Settings(), window=window, length_bars=length)


def test_worker_snapshot_and_result_keep_request_identity_and_original_audio(qapp, memory_track):
    settings = Settings(candidates_per_track=2, max_one_shot_seconds=0.2)
    worker = workers.CandidateSearchWorker(41, memory_track, settings, window=(2.0, 18.0), length_bars=2.0)
    settings.candidates_per_track = 1
    settings.max_one_shot_seconds = 0.01
    results, errors = [], []
    worker.finished.connect(results.append)
    worker.failed.connect(errors.append)
    worker.run()
    assert errors == [] and len(results) == 1
    result = results[0]
    assert result.request_id == 41 and result.window == (2.0, 18.0) and result.length_bars == 2.0
    assert result.loaded is not memory_track and result.loaded.samples is memory_track.samples
    assert result.loaded.analysis is memory_track.analysis and result.loaded.sample_rate == 1000
    assert len(result.loaded.candidates) == 4 and isinstance(result.message, str)
    assert max(
        c.duration_seconds for c in result.loaded.candidates if c.type is CandidateType.ONE_SHOT
    ) == pytest.approx(0.2)
    assert settings.candidates_per_track == 1 and settings.max_one_shot_seconds == 0.01
    with pytest.raises(FrozenInstanceError):
        result.request_id = 42


def test_worker_snapshots_automatic_loop_settings(qapp, memory_track):
    settings = Settings(loop_lengths_bars=(0.25, 1.0), candidates_per_track=2)
    worker = workers.CandidateSearchWorker(42, memory_track, settings)
    settings.loop_lengths_bars = (0.5,)
    results = []
    worker.finished.connect(results.append)
    worker.run()
    assert len(results) == 1
    result = results[0]
    assert result.request_id == 42 and result.window is result.length_bars is None
    assert {c.bars for c in result.loaded.candidates if c.type is CandidateType.LOOP} == {0.25, 1.0}


@pytest.mark.parametrize("invalid", [False, True])
@pytest.mark.parametrize("attempt", range(12))
def test_candidate_worker_thread_really_finishes_on_result_or_error(qapp, memory_track, invalid, attempt):
    worker = workers.CandidateSearchWorker(
        43, memory_track, Settings(), window=(0.0, 0.6), length_bars=None if invalid else 4.0
    )
    results, errors, finished = [], [], []
    worker.finished.connect(results.append)
    worker.failed.connect(errors.append)
    thread = workers.start_in_thread(worker)
    loop = QEventLoop()
    thread.finished.connect(lambda: finished.append(True))
    thread.finished.connect(loop.quit)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(5000)
    thread.start()
    loop.exec()
    timeout.stop()
    if not finished:
        thread.quit()
        thread.wait(5000)
    assert finished == [True], "Worker emitted no actual QThread.finished signal"
    if invalid:
        assert len(errors) == 1 and "length" in errors[0].lower() and results == []
    else:
        assert errors == [] and len(results) == 1 and results[0].request_id == 43
