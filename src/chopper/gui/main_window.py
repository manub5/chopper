from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from chopper.core import audio_io
from chopper.core.cache import AnalysisCache
from chopper.core.exporting import export_batch, export_drag
from chopper.core.models import Track
from chopper.core.settings import (
    Settings,
    default_cache_path,
    load_settings,
    save_settings,
)
from chopper.gui.actions import ActionRegistry
from chopper.gui.candidates_panel import CandidatesPanel
from chopper.gui.export_folder_dialog import choose_export_folder
from chopper.gui.library_panel import LibraryPanel
from chopper.gui.presentation import LoadedTrack
from chopper.gui.preview_player import PreviewPlayer
from chopper.gui.sample_drag import start_file_drag
from chopper.gui.sample_lanes import SampleLanesView
from chopper.gui.sample_state import SampleState
from chopper.gui.settings_dialog import SettingsDialog
from chopper.gui.theme import ThemeManager
from chopper.gui.waveform_view import WaveformView
from chopper.gui.workers import (
    AlbumAnalysisWorker,
    TrackAnalysisWorker,
    start_in_thread,
)


class MainWindow(QMainWindow):
    """Fenêtre principale : bibliothèque, forme d'onde, candidats, paramètres."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache: AnalysisCache | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Chopper")
        self.resize(1100, 700)

        self.settings = settings if settings is not None else load_settings()
        self.cache = cache if cache is not None else AnalysisCache(default_cache_path())

        self._current_track: Track | None = None
        self._current_folder: Path | None = None
        self._thread: QThread | None = None
        self._analysis_busy = False
        # Référence gardée : PySide6 ne garde pas le worker en vie tout seul (voir
        # _run_worker) une fois qu'il n'y a plus de variable Python qui le référence.
        self._worker: TrackAnalysisWorker | AlbumAnalysisWorker | None = None

        self.library_panel = LibraryPanel()
        self.waveform_view = WaveformView()
        self.sample_state = SampleState(auto_play=self.settings.auto_play, parent=self)
        self.preview_player = PreviewPlayer(self)
        self.sample_state.play_requested.connect(self._play_sample)
        self.sample_state.stop_requested.connect(self.preview_player.stop)
        self.sample_state.error_reported.connect(self._on_preview_failed)
        self.preview_player.started.connect(self.sample_state.playback_started)
        self.preview_player.finished.connect(self.sample_state.playback_finished)
        self.preview_player.failed.connect(self.sample_state.playback_failed)
        self.candidates_panel = CandidatesPanel(self.sample_state)
        self.sample_lanes = SampleLanesView(self.sample_state)
        self.sample_lanes.link_time_axis(self.waveform_view)
        self.sample_state.changed.connect(self._sync_playback_highlight)
        self.track_label = QLabel()
        font = self.track_label.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.track_label.setFont(font)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        open_library_button = QPushButton("Open library…")

        self.analyze_album_button = QPushButton("Analyze album")
        self.analyze_album_button.setEnabled(False)

        settings_button = QPushButton("Settings…")

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(open_library_button)
        self.auto_play_checkbox = QCheckBox("Auto-preview")
        self.auto_play_checkbox.setChecked(self.settings.auto_play)
        self.auto_play_checkbox.toggled.connect(self._on_auto_play_toggled)
        top_buttons.addWidget(self.auto_play_checkbox)
        top_buttons.addWidget(self.analyze_album_button)
        top_buttons.addStretch(1)
        top_buttons.addWidget(settings_button)

        right_panel = QWidget()
        self.candidate_scope = right_panel
        right_panel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.sample_lanes.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.track_label)
        right_layout.addWidget(self.waveform_view, 3)
        right_layout.addWidget(self.sample_lanes, 1)
        right_layout.addWidget(self.candidates_panel, 1)
        right_layout.addWidget(self.progress_bar)

        splitter = QSplitter()
        splitter.addWidget(self.library_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 850])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addLayout(top_buttons)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.library_panel.track_selected.connect(self._on_track_selected)
        self.library_panel.folder_selected.connect(self._on_folder_selected)
        self.library_panel.load_failed.connect(self._on_library_load_failed)
        self.action_registry = ActionRegistry(self, right_panel)
        actions = self.action_registry.actions
        actions["open_library"].triggered.connect(self._on_open_library_clicked)
        actions["settings"].triggered.connect(self._on_settings_clicked)
        actions["analyze_album"].triggered.connect(self._on_analyze_album_clicked)
        actions["quit"].triggered.connect(self.close)
        actions["play"].triggered.connect(self.sample_state.toggle_playback)
        actions["stop"].triggered.connect(self.sample_state.stop)
        actions["mark"].triggered.connect(self._mark_active_sample)
        actions["mark_all"].triggered.connect(self.sample_state.mark_all)
        actions["clear_marks"].triggered.connect(self.sample_state.clear_marks)
        actions["export_marked"].triggered.connect(lambda: self._on_export_requested("marked"))
        actions["export_all"].triggered.connect(lambda: self._on_export_requested("all"))
        self.candidates_panel.export_requested.connect(lambda mode: actions[f"export_{mode}"].trigger())
        self.action_registry.bind_button(open_library_button, "open_library")
        self.action_registry.bind_button(settings_button, "settings")
        self.action_registry.bind_button(self.analyze_album_button, "analyze_album")
        self.action_registry.bind_button(
            self.candidates_panel.export_marked_button, "export_marked", connect_click=False
        )
        self.action_registry.bind_button(
            self.candidates_panel.export_all_button, "export_all", connect_click=False
        )
        self.sample_state.changed.connect(self._sync_actions)
        self._sync_actions()
        self.candidates_panel.drag_requested.connect(self._on_drag_requested)

        self.theme_manager = ThemeManager(force_dark=self.settings.force_dark, parent=self)
        self.theme_manager.changed.connect(self._apply_theme)
        self._apply_theme()

        if self.settings.library_root:
            self.library_panel.set_root(Path(self.settings.library_root))

    # --- bibliothèque ---------------------------------------------------

    def _on_open_library_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Library folder")
        if not directory:
            return
        self.settings.library_root = directory
        save_settings(self.settings)
        self.library_panel.set_root(Path(directory))

    def _on_folder_selected(self, folder: Path) -> None:
        self._current_folder = folder
        self._sync_actions()

    def _on_library_load_failed(self, folder: Path, message: str) -> None:
        self.status_bar.showMessage(f"Could not read {folder}: {message}", 8000)

    # --- analyse d'une piste ---------------------------------------------

    def _on_track_selected(self, path: Path) -> None:
        if self._is_analysis_running():
            # Une analyse (piste ou album) est déjà en cours : la bibliothèque est
            # désactivée pendant ce temps (voir _set_busy), donc ce cas ne devrait
            # arriver que par un appel programmatique. Deux QThread simultanés sur
            # le même MainWindow ont déjà fait planter l'appli en pratique (le
            # second écrase la seule référence Python vers le premier, encore en
            # cours) : on refuse plutôt que de risquer ça.
            self.status_bar.showMessage("Analysis is already running. Please wait.", 4000)
            return

        track = audio_io.read_track(path)
        self.sample_state.clear()
        self.track_label.clear()
        self.waveform_view.clear()
        self._current_track = track
        self.status_bar.showMessage(f"Analyzing {track.title}…")

        worker = TrackAnalysisWorker(track, self.settings, self.cache)
        worker.finished.connect(self._on_track_analyzed)
        worker.failed.connect(self._on_track_failed)
        self._set_busy(True)
        self._run_worker(worker)

    def _on_track_analyzed(self, result: LoadedTrack) -> None:
        self._set_busy(False)
        analysis = result.analysis
        samples, sample_rate = result.samples, result.sample_rate
        candidates = list(result.candidates)

        self.waveform_view.set_waveform(samples, sample_rate)
        self.waveform_view.set_downbeats(analysis.downbeat_times)
        self.sample_state.load_track(result)
        self.track_label.setText(f"{analysis.track.title} — {analysis.tempo_bpm:.1f} BPM")

        sample_word = "sample" if len(candidates) == 1 else "samples"
        self.status_bar.showMessage(
            f"{analysis.track.title} — {analysis.tempo_bpm:.1f} BPM, {len(candidates)} {sample_word}",
            5000,
        )

    def _on_track_failed(self, message: str) -> None:
        self._set_busy(False)
        self.status_bar.showMessage(f"Analysis failed: {message}", 8000)

    # --- analyse d'un album entier ---------------------------------------

    def _on_analyze_album_clicked(self) -> None:
        if self._is_analysis_running():
            self.status_bar.showMessage("Analysis is already running. Please wait.", 4000)
            return

        if self._current_folder is None:
            QMessageBox.information(self, "Chopper", "Select an album folder first.")
            return

        # Le dossier est parcouru dans le worker (voir AlbumAnalysisWorker.run), pas ici :
        # sur un dossier réseau avec des milliers de pistes, lire les tags de chacune
        # peut prendre du temps, et ça ne doit pas geler l'interface avant même que la
        # barre de progression n'apparaisse.
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indéterminée tant que le dossier n'est pas encore scanné
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Finding album tracks…")

        worker = AlbumAnalysisWorker(self._current_folder, self.settings, self.cache)
        worker.scan_done.connect(self._on_album_scan_done)
        worker.scan_failed.connect(self._on_album_scan_failed)
        worker.progress.connect(self._on_album_progress)
        worker.track_failed.connect(self._on_album_track_failed)
        worker.finished.connect(self._on_album_finished)
        self._set_busy(True)
        self._run_worker(worker)

    def _on_album_scan_done(self, total: int) -> None:
        if total == 0:
            self.status_bar.showMessage("No audio files in this folder.", 5000)
            return
        self.progress_bar.setRange(0, total)

    def _on_album_scan_failed(self, message: str) -> None:
        self.status_bar.showMessage(f"Folder is no longer available: {message}", 8000)

    def _on_album_progress(self, done: int, total: int) -> None:
        self.progress_bar.setValue(done)
        self.status_bar.showMessage(f"Analyzing album: {done}/{total} tracks")

    def _on_album_track_failed(self, track: Track, message: str) -> None:
        self.status_bar.showMessage(f"{track.title}: analysis failed ({message})", 8000)

    def _on_album_finished(self) -> None:
        # Si le dossier était vide, _on_album_scan_done a déjà affiché un message
        # explicite (progress_bar.maximum() est resté à 0, jamais mis à jour) :
        # ne pas l'effacer aussitôt par un "terminée" générique et peu informatif.
        had_tracks = self.progress_bar.maximum() > 0
        self._set_busy(False)
        self.progress_bar.setVisible(False)
        if had_tracks:
            self.status_bar.showMessage("Album analysis complete", 5000)

    # --- paramètres -------------------------------------------------------

    def _on_settings_clicked(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings()
            self.auto_play_checkbox.setChecked(self.settings.auto_play)
            self.theme_manager.set_force_dark(self.settings.force_dark)
            save_settings(self.settings)

    def _apply_theme(self) -> None:
        palette = self.theme_manager.palette
        self.setPalette(palette.to_qpalette())
        self.waveform_view.apply_theme(palette)
        self.sample_lanes.apply_theme(palette)
        self.candidates_panel.apply_theme(palette)

    # --- préécoute -------------------------------------------------------

    def _mark_active_sample(self) -> None:
        if self.sample_state.active_id is not None:
            self.sample_state.toggle_mark(self.sample_state.active_id)

    def _sync_actions(self) -> None:
        state = self.sample_state
        available = {
            "analyze_album": self._current_folder is not None and not self._analysis_busy,
            "play": state.active_id is not None,
            "stop": state.playing_id is not None,
            "mark": state.active_id is not None,
            "mark_all": bool(state.items),
            "clear_marks": bool(state.marked_ids),
            "export_marked": bool(state.marked_ids),
            "export_all": bool(state.items),
        }
        for name, enabled in available.items():
            self.action_registry.set_available(name, enabled)

    def _on_preview_failed(self, message: str) -> None:
        self.status_bar.showMessage(message, 8000)

    def _on_auto_play_toggled(self, enabled: bool) -> None:
        self.sample_state.set_auto_play(enabled)
        self.settings.auto_play = enabled
        save_settings(self.settings)

    def _play_sample(self, item_id: int, token: int) -> None:
        loaded = self.sample_state.loaded_track
        if loaded is not None:
            item = next(item for item in self.sample_state.items if item.id == item_id)
            self.preview_player.play(loaded.samples, loaded.sample_rate, item.candidate, token)

    def _sync_playback_highlight(self) -> None:
        candidate = next(
            (item.candidate for item in self.sample_state.items if item.id == self.sample_state.playing_id),
            None,
        )
        self.waveform_view.set_playing_candidate(candidate)

    # --- export -------------------------------------------------------

    def _ensure_export_directory(self) -> Path | None:
        if self.settings.export_dir:
            return Path(self.settings.export_dir)
        directory = choose_export_folder(self)
        if directory is None:
            return None
        updated = replace(self.settings, export_dir=str(directory))
        try:
            save_settings(updated)
        except Exception as exc:  # noqa: BLE001 - report persistence failures before writing any audio
            self.status_bar.showMessage(f"Could not save the sample folder: {exc}", 10000)
            return None
        self.settings = updated
        return directory

    def _on_export_requested(self, mode: str) -> None:
        loaded = self.sample_state.loaded_track
        if loaded is None or mode not in {"marked", "all"}:
            return
        candidates = tuple(
            item.candidate
            for item in self.sample_state.items
            if mode == "all" or item.id in self.sample_state.marked_ids
        )
        if not candidates:
            QMessageBox.information(self, "Chopper", "No samples marked for export.")
            return

        directory = self._ensure_export_directory()
        if directory is None:
            return

        report = export_batch(
            loaded.samples,
            loaded.sample_rate,
            loaded.analysis.track,
            candidates,
            directory,
            file_format=self.settings.export_format,
        )
        file_word = "file" if len(report.paths) == 1 else "files"
        if report.error is not None:
            message = f"Export failed: {report.error}"
            if report.paths:
                names = ", ".join(path.name for path in report.paths)
                message = f"Partial export: {len(report.paths)} {file_word} kept: {names}. {report.error}"
            self.status_bar.setToolTip(message)
            self.status_bar.showMessage(message, 10000)
        else:
            self.status_bar.setToolTip("")
            self.status_bar.showMessage(f"Exported {len(report.paths)} {file_word}", 5000)

    def _on_drag_requested(self, item_id: int) -> None:
        loaded = self.sample_state.loaded_track
        item = next((item for item in self.sample_state.items if item.id == item_id), None)
        if loaded is None or item is None:
            return
        needed_setup = not self.settings.export_dir
        directory = self._ensure_export_directory()
        if directory is None:
            return
        if needed_setup:
            self.status_bar.showMessage(
                "Sample folder saved. Drag the sample again to send it to your DAW.", 10000
            )
            return
        try:
            path = export_drag(
                loaded.samples,
                loaded.sample_rate,
                loaded.analysis.track,
                item.candidate,
                directory,
            )
        except Exception as exc:  # noqa: BLE001 - never start a drag after a writer failure
            self.status_bar.showMessage(f"Could not create drag WAV: {exc}", 10000)
            return
        try:
            start_file_drag(self.candidates_panel.table, path)
        except Exception as exc:  # noqa: BLE001 - the file must remain even if the platform transfer fails
            self.status_bar.showMessage(f"WAV kept: {path}; drag failed: {exc}", 10000)
        else:
            # Qt's returned action is not proof that a DAW successfully imported it.
            self.status_bar.showMessage(f"WAV kept: {path}", 10000)

    # --- infrastructure -------------------------------------------------

    def _is_analysis_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _set_busy(self, busy: bool) -> None:
        """Empêche de lancer une deuxième analyse pendant qu'une autre tourne déjà :
        deux QThread simultanés sur cette fenêtre se sont déjà marché dessus en
        pratique (voir _run_worker)."""
        self._analysis_busy = busy
        self.library_panel.setEnabled(not busy)
        self.analyze_album_button.setEnabled(not busy and self._current_folder is not None)
        self.action_registry.set_available("analyze_album", not busy and self._current_folder is not None)

    def _run_worker(self, worker: TrackAnalysisWorker | AlbumAnalysisWorker) -> None:
        self._worker = worker  # évite que Python ne le détruise pendant l'exécution
        self._thread = start_in_thread(worker)
        self._thread.finished.connect(self._on_worker_thread_finished)
        self._thread.start()

    def _on_worker_thread_finished(self) -> None:
        # thread.finished n'est émis qu'une fois le thread réellement arrêté
        # (exec() revenu), contrairement à worker.finished (traité par
        # _on_track_analyzed / _on_album_finished) qui peut encore s'exécuter
        # alors que thread.quit() n'a pas encore été traité. Relâcher la
        # référence dès worker.finished a provoqué un vrai plantage (le
        # thread encore vivant se faisait détruire sous nos pieds) ; ici,
        # c'est sûr.
        self._thread = None
        self._worker = None

    def closeEvent(self, event) -> None:
        self.sample_state.stop()
        self.preview_player.stop()
        if isinstance(self._worker, AlbumAnalysisWorker):
            # Demande l'arrêt après la piste en cours plutôt que de laisser tourner
            # tout le reste de l'album pendant qu'on ferme la fenêtre.
            self._worker.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            # Pas de timeout court ici : le thread peut être en plein milieu d'une
            # analyse (rythme CPU, cf. CLAUDE.md "sans GPU") qui dure largement
            # plus de 2 s. Fermer le cache SQLite pendant qu'il l'utilise encore
            # (voir core/cache.py) provoquerait des erreurs sur les pistes
            # restantes. On attend donc la vraie fin, avec une limite large plutôt
            # qu'absente pour ne pas bloquer indéfiniment sur un dossier réseau
            # devenu injoignable en cours d'analyse.
            self._thread.wait(30_000)
        self.cache.close()
        super().closeEvent(event)
