from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from chopper.core import audio_io, onsets, rhythm
from chopper.core import candidates as candidates_module
from chopper.core.audio_io import AUDIO_EXTENSIONS
from chopper.core.cache import AnalysisCache
from chopper.core.models import Analysis, Candidate, Track, is_loop_length
from chopper.core.settings import Settings
from chopper.gui.presentation import CandidateSearchResult, LoadedTrack, Window


def tracks_in_folder(folder: Path) -> list[Track]:
    """Pistes audio directement dans `folder` (un seul niveau, voir gui/library_panel.py),
    triées par nom. Lit les tags de chaque fichier (mutagen) : sur un dossier réseau
    avec des milliers de pistes, ça peut prendre du temps — à appeler depuis un thread
    d'arrière-plan (voir AlbumAnalysisWorker), jamais depuis le thread de l'interface."""
    paths = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
    return [audio_io.read_track(p) for p in paths]


@dataclass(frozen=True)
class ChopOptions:
    start: float = 0.0
    end: float | None = None
    bars: float | None = None
    one_shot_duration: float | None = None
    max_samples: int | None = None
    export_dir: Path | None = None

    def window(self, sample_rate: int, frame_count: int) -> Window:
        duration = frame_count / sample_rate
        end = duration if self.end is None else self.end
        if not 0 <= self.start < end <= duration:
            raise ValueError(f"Chop range must satisfy 0 <= start < end <= {duration:.9g} seconds.")
        if round(self.start * sample_rate) >= round(end * sample_rate):
            raise ValueError("Chop range must contain at least one audio frame.")
        return self.start, end

    def apply(self, settings: Settings) -> Settings:
        return replace(
            settings,
            loop_lengths_bars=settings.loop_lengths_bars if self.bars is None else (self.bars,),
            one_shot_duration_seconds=(
                settings.one_shot_duration_seconds
                if self.one_shot_duration is None
                else self.one_shot_duration
            ),
            candidates_per_track=settings.candidates_per_track
            if self.max_samples is None
            else self.max_samples,
        )


def analyze_track(
    track: Track, settings: Settings, cache: AnalysisCache | None = None, *, window: Window | None = None
) -> tuple[Analysis, list[Candidate]]:
    """Pipeline complet pour une piste : rythme + onsets (via le cache si possible),
    puis sélection des candidats boucles et one-shots."""
    analysis = cache.get(track) if cache else None
    samples, sample_rate = audio_io.load(track.path)

    if analysis is None:
        device = rhythm.resolve_device(settings.gpu_mode)
        tempo_bpm, beat_times, downbeat_times = rhythm.analyze_rhythm(track.path, device=device)
        onset_times = onsets.detect_onsets(samples, sample_rate)
        analysis = Analysis(
            track=track,
            tempo_bpm=tempo_bpm,
            beat_times=beat_times,
            downbeat_times=downbeat_times,
            onset_times=onset_times,
        )
        if cache:
            cache.set(analysis)

    loops = candidates_module.find_loop_candidates(
        samples,
        sample_rate,
        analysis.tempo_bpm,
        analysis.downbeat_times,
        lengths_bars=settings.loop_lengths_bars,
        max_candidates=settings.candidates_per_track,
        window=window,
    )
    shots = candidates_module.find_one_shot_candidates(
        samples,
        sample_rate,
        analysis.onset_times,
        duration_seconds=settings.one_shot_duration_seconds,
        max_candidates=settings.candidates_per_track,
        window=window,
    )
    all_candidates = sorted(loops + shots, key=lambda c: c.score, reverse=True)
    return analysis, all_candidates


def search_candidates(
    loaded: LoadedTrack,
    settings: Settings,
    *,
    window: Window | None = None,
    length_bars: float | None = None,
) -> tuple[tuple[Candidate, ...], str]:
    """Re-rank cached rhythm/onsets against the original in-memory audio only."""
    if window is None:
        if length_bars is not None:
            raise ValueError("A manual loop length requires a selection window.")
        lengths = settings.loop_lengths_bars
    else:
        if length_bars is None or not is_loop_length(length_bars):
            raise ValueError("Select a supported manual loop length.")
        lengths = (float(length_bars),)
    analysis = loaded.analysis
    loops = candidates_module.find_loop_candidates(
        loaded.samples,
        loaded.sample_rate,
        analysis.tempo_bpm,
        analysis.downbeat_times,
        lengths_bars=lengths,
        max_candidates=settings.candidates_per_track,
        window=window,
    )
    shots = candidates_module.find_one_shot_candidates(
        loaded.samples,
        loaded.sample_rate,
        analysis.onset_times,
        duration_seconds=settings.one_shot_duration_seconds,
        max_candidates=settings.candidates_per_track,
        window=window,
    )
    found = tuple(sorted(loops + shots, key=lambda candidate: candidate.score, reverse=True))
    message = f"Found {len(loops)} loops and {len(shots)} one-shots." if found else "No samples found."
    if window is not None:
        bar_duration = (
            float(np.median(np.diff(analysis.downbeat_times))) if len(analysis.downbeat_times) >= 2 else 0.0
        )
        if analysis.tempo_bpm <= 0 or not np.isfinite(bar_duration) or bar_duration <= 0:
            explanation = "No usable downbeat grid."
        elif window[1] - window[0] < bar_duration * lengths[0]:
            explanation = f"Selection too short for {lengths[0]:g}-bar loops."
        else:
            explanation = ""
        if explanation:
            message = f"{explanation} Found {len(shots)} one-shots."
            if not found:
                message = f"No samples found. {message}"
    return found, message


class CandidateSearchWorker(QObject):
    """Search cached data with a settings snapshot and a caller-owned request ID."""

    finished = Signal(object)  # CandidateSearchResult
    failed = Signal(str)

    def __init__(
        self,
        request_id: int,
        loaded: LoadedTrack,
        settings: Settings,
        *,
        window: Window | None = None,
        length_bars: float | None = None,
    ):
        super().__init__()
        self._request_id = request_id
        self._loaded = loaded
        self._settings = deepcopy(settings)
        self._window = window
        self._length_bars = length_bars

    @property
    def request_id(self) -> int:
        return self._request_id

    @Slot()
    def run(self) -> None:
        try:
            candidates, message = search_candidates(
                self._loaded, self._settings, window=self._window, length_bars=self._length_bars
            )
            result = CandidateSearchResult(
                self._request_id,
                replace(self._loaded, candidates=candidates),
                self._window,
                self._length_bars,
                message,
            )
        except Exception as exc:  # noqa: BLE001 - report worker failures to the interface
            self.failed.emit(str(exc))
        else:
            self.finished.emit(result)


class TrackAnalysisWorker(QObject):
    """Analyse une piste ; à déplacer dans un QThread pour ne pas geler l'interface."""

    finished = Signal(object)  # LoadedTrack
    failed = Signal(str)

    def __init__(
        self,
        track: Track,
        settings: Settings,
        cache: AnalysisCache | None = None,
        *,
        chop: ChopOptions | None = None,
    ):
        super().__init__()
        self._track = track
        self._settings = settings
        self._cache = cache
        self.chop = chop

    def run(self) -> None:
        try:
            if self.chop is None:
                analysis, candidates = analyze_track(self._track, self._settings, self._cache)
                samples, sample_rate = audio_io.load(self._track.path, mono=False)
            else:
                samples, sample_rate = audio_io.load(self._track.path, mono=False)
                window = self.chop.window(sample_rate, len(samples))
                analysis, candidates = analyze_track(
                    self._track, self.chop.apply(self._settings), self._cache, window=window
                )
        except Exception as exc:  # noqa: BLE001 - remonté à l'interface plutôt qu'avalé
            self.failed.emit(str(exc))
        else:
            self.finished.emit(LoadedTrack(analysis, tuple(candidates), samples, sample_rate))


class AlbumAnalysisWorker(QObject):
    """Analyse toutes les pistes audio d'un dossier l'une après l'autre, avec progression.

    Le dossier est parcouru (et les tags de chaque piste lus) ici, dans run(),
    pas avant : sur un dossier réseau avec des milliers de pistes, ce
    parcours peut prendre du temps, et il ne doit jamais bloquer le thread
    de l'interface pendant qu'on affiche la barre de progression.
    """

    scan_done = Signal(int)  # nombre de pistes trouvées, une fois le dossier parcouru
    scan_failed = Signal(str)  # le dossier lui-même est devenu illisible (ex. NAS déconnecté)
    progress = Signal(int, int)  # (pistes traitées, total)
    track_done = Signal(object, list)  # Analysis, list[Candidate]
    track_failed = Signal(object, str)  # Track, message
    finished = Signal()

    def __init__(self, folder: Path, settings: Settings, cache: AnalysisCache | None = None):
        super().__init__()
        self._folder = folder
        self._settings = settings
        self._cache = cache
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            tracks = tracks_in_folder(self._folder)
        except OSError as exc:
            # Le dossier lui-même est devenu illisible en cours de route (NAS
            # déconnecté, dossier supprimé...) : sans ce garde-fou, l'exception
            # tuait run() avant finished.emit(), et plus rien ne redémarrait
            # jamais l'interface (bouton et bibliothèque restaient désactivés
            # indéfiniment, aucun signal pour le signaler).
            self.scan_failed.emit(str(exc))
            self.finished.emit()
            return

        self.scan_done.emit(len(tracks))

        total = len(tracks)
        for index, track in enumerate(tracks, start=1):
            if self._stop_requested:
                break
            try:
                analysis, candidates = analyze_track(track, self._settings, self._cache)
            except Exception as exc:  # noqa: BLE001 - une piste en erreur ne doit pas arrêter l'album
                self.track_failed.emit(track, str(exc))
            else:
                self.track_done.emit(analysis, candidates)
            self.progress.emit(index, total)
        self.finished.emit()


def start_in_thread(worker: TrackAnalysisWorker | AlbumAnalysisWorker | CandidateSearchWorker) -> QThread:
    """Câblage standard Qt : lance worker.run() dans un nouveau QThread au démarrage,
    et arrête le thread sur succès comme sur échec."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    if isinstance(worker, (TrackAnalysisWorker, CandidateSearchWorker)):
        worker.failed.connect(thread.quit)
    # The caller retains the worker until thread.finished, not just its result.
    thread.finished.connect(thread.deleteLater)
    return thread
