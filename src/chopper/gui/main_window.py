from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt, QThread, Slot
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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
from chopper.core.models import Candidate, CandidateType, Track
from chopper.core.settings import (
    Settings,
    default_cache_path,
    load_settings,
    save_settings,
)
from chopper.gui.actions import ActionRegistry
from chopper.gui.bpm_dialog import choose_bpm
from chopper.gui.candidates_panel import CandidatesPanel
from chopper.gui.export_folder_dialog import choose_export_folder
from chopper.gui.library_panel import LibraryPanel
from chopper.gui.presentation import (
    LOOP_LENGTH_CHOICES,
    CandidateSearchResult,
    LoadedTrack,
    Window,
    format_time,
)
from chopper.gui.preview_player import PreviewPlayer
from chopper.gui.sample_drag import start_file_drag
from chopper.gui.sample_lanes import SampleLanesView
from chopper.gui.sample_state import SampleState
from chopper.gui.selection_controller import SelectionController
from chopper.gui.selection_dialog import confirm_selection_transition
from chopper.gui.settings_dialog import SettingsDialog
from chopper.gui.theme import ThemeManager
from chopper.gui.waveform_view import WaveformView
from chopper.gui.workers import (
    AlbumAnalysisWorker,
    CandidateSearchWorker,
    ChopOptions,
    TrackAnalysisWorker,
    start_in_thread,
)


class _SampleWorkspaceSplitter(QSplitter):
    _INITIAL_SIZES = (270, 120, 510)

    def __init__(self, waveform: QWidget, lanes: QWidget, table: QWidget) -> None:
        super().__init__(Qt.Orientation.Vertical)
        self._lanes = lanes
        self._lane_height: int | None = None
        self._moved_while_hidden = False
        self.setChildrenCollapsible(False)
        for view in (waveform, lanes, table):
            self.addWidget(view)
        for index in (1, 2):
            self.handle(index).setCursor(Qt.CursorShape.SizeVerCursor)
        self.setSizes(self._INITIAL_SIZES)
        lanes.installEventFilter(self)
        self.splitterMoved.connect(self._record_move)

    def _record_move(self, _position: int, _index: int) -> None:
        if self._lanes.isHidden():
            self._moved_while_hidden = True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._lanes:
            if event.type() == QEvent.Type.HideToParent:
                self._lane_height = self._lanes.height()
            elif event.type() == QEvent.Type.ShowToParent and self._moved_while_hidden:
                self._moved_while_hidden = False
                # Qt forgets the hidden child's allocation when the handle moves.
                available = self.contentsRect().height() - 2 * self.handleWidth()
                height = self._lane_height
                if height is None:
                    height = round(available * self._INITIAL_SIZES[1] / sum(self._INITIAL_SIZES))
                wave, _, table = self.sizes()
                rest = max(0, available - height)
                wave_height = round(rest * wave / max(1, wave + table))
                self.setSizes([wave_height, height, rest - wave_height])
        return super().eventFilter(watched, event)


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
        self.setAcceptDrops(True)

        self.settings = settings if settings is not None else load_settings()
        self.cache = cache if cache is not None else AnalysisCache(default_cache_path())

        self._current_track: Track | None = None
        self._opening_external_track = False
        self._current_folder: Path | None = None
        self._thread: QThread | None = None
        self._analysis_busy = False
        self._closing = False
        self._search_request_id: int | None = None
        # Référence gardée : PySide6 ne garde pas le worker en vie tout seul (voir
        # _run_worker) une fois qu'il n'y a plus de variable Python qui le référence.
        self._worker: TrackAnalysisWorker | AlbumAnalysisWorker | CandidateSearchWorker | None = None

        self.library_panel = LibraryPanel()
        self.waveform_view = WaveformView()
        self.sample_state = SampleState(auto_play=self.settings.auto_play, parent=self)
        self.selection_controller = SelectionController(
            self.sample_state,
            choose=lambda action, can_export: confirm_selection_transition(self, action, can_export),
            export_all=self._export_manual_candidates,
            parent=self,
        )
        self.selection_controller.search_requested.connect(self._start_candidate_search)
        self.waveform_view.selection_finished.connect(self.selection_controller.set_selection)
        self.waveform_view.selection_invalidated.connect(self.selection_controller.invalidate_selection)
        self.preview_player = PreviewPlayer(self)
        self.sample_state.play_requested.connect(self._play_sample)
        self.sample_state.range_play_requested.connect(self._play_range)
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
        selection_bar = QHBoxLayout()
        selection_bar.addWidget(QLabel("Length"))
        self.length_combo = QComboBox()
        for bars, label in LOOP_LENGTH_CHOICES:
            self.length_combo.addItem(label, bars)
        self.length_combo.setCurrentIndex(2)
        self.length_combo.currentIndexChanged.connect(
            lambda index: self.selection_controller.set_length(self.length_combo.itemData(index))
        )
        selection_bar.addWidget(self.length_combo)
        self.chop_selection_button = QPushButton("Chop selection")
        self.chop_selection_button.setProperty("materialPrimary", True)
        self.whole_track_button = QPushButton("Whole track")
        selection_bar.addWidget(self.chop_selection_button)
        selection_bar.addWidget(self.whole_track_button)
        selection_bar.addStretch(1)
        right_layout.addLayout(selection_bar)
        self.selection_label = QLabel()
        self.selection_label.setWordWrap(True)
        self.selection_status_label = QLabel()
        self.selection_status_label.setWordWrap(True)
        right_layout.addWidget(self.selection_label)
        right_layout.addWidget(self.selection_status_label)
        sample_splitter = _SampleWorkspaceSplitter(
            self.waveform_view, self.sample_lanes, self.candidates_panel
        )
        right_layout.addWidget(sample_splitter, 1)
        right_layout.addWidget(self.progress_bar)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.library_panel)
        splitter.addWidget(right_panel)
        splitter.handle(1).setCursor(Qt.CursorShape.SizeHorCursor)
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
        actions["add_album"].triggered.connect(self._on_add_album_clicked)
        actions["open_track"].triggered.connect(self._on_open_track_clicked)
        actions["settings"].triggered.connect(self._on_settings_clicked)
        actions["analyze_album"].triggered.connect(self._on_analyze_album_clicked)
        actions["quit"].triggered.connect(self.close)
        actions["play"].triggered.connect(self.sample_state.toggle_playback)
        actions["stop"].triggered.connect(self._stop_or_leave_selection)
        actions["chop_selection"].triggered.connect(self.selection_controller.request_chop)
        actions["whole_track"].triggered.connect(self.selection_controller.request_whole_track)
        actions["mark"].triggered.connect(self._mark_active_sample)
        actions["mark_all"].triggered.connect(self.sample_state.mark_all)
        actions["clear_marks"].triggered.connect(self.sample_state.clear_marks)
        actions["export_marked"].triggered.connect(lambda: self._on_export_requested("marked"))
        actions["export_all"].triggered.connect(lambda: self._on_export_requested("all"))
        self.candidates_panel.export_requested.connect(lambda mode: actions[f"export_{mode}"].trigger())
        self.candidates_panel.sample_export_requested.connect(self._on_sample_export_requested)
        self.sample_lanes.sample_export_requested.connect(self._on_sample_export_requested)
        self.action_registry.bind_button(open_library_button, "open_library")
        self.action_registry.bind_button(settings_button, "settings")
        self.action_registry.bind_button(self.analyze_album_button, "analyze_album")
        self.action_registry.bind_button(self.chop_selection_button, "chop_selection")
        self.action_registry.bind_button(self.whole_track_button, "whole_track")
        self.action_registry.bind_button(
            self.candidates_panel.export_marked_button, "export_marked", connect_click=False
        )
        self.action_registry.bind_button(
            self.candidates_panel.export_all_button, "export_all", connect_click=False
        )
        self.sample_state.changed.connect(self._sync_actions)
        self.selection_controller.changed.connect(self._sync_selection)
        self._sync_selection()
        self._sync_actions()
        self.candidates_panel.drag_requested.connect(self._on_drag_requested)
        self.candidates_panel.boundary_edit_requested.connect(self._edit_sample_boundary)
        self.candidates_panel.bpm_edit_requested.connect(self._edit_sample_bpm)

        self.theme_manager = ThemeManager(force_dark=self.settings.force_dark, parent=self)
        self.theme_manager.changed.connect(self._apply_theme)
        self._apply_theme()

        if self.settings.library_root:
            self.library_panel.set_root(Path(self.settings.library_root))

    # --- bibliothèque ---------------------------------------------------

    def _on_open_library_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Library folder", self.settings.dialog_start("library")
        )
        if not directory:
            return
        updated = replace(self.settings, library_root=directory)
        updated.remember_dialog("library", Path(directory))
        self._save_preferences(updated)
        self.library_panel.set_root(Path(directory))

    def _on_add_album_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Add album folder", self.settings.dialog_start("album")
        )
        if directory:
            updated = replace(self.settings)
            updated.remember_dialog("album", Path(directory))
            self._save_preferences(updated)
            self.open_path(Path(directory))

    def _on_open_track_clicked(self) -> None:
        extensions = " ".join(f"*{suffix}" for suffix in sorted(audio_io.AUDIO_EXTENSIONS))
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open track", self.settings.dialog_start("track"), f"Audio files ({extensions})"
        )
        if filename:
            updated = replace(self.settings)
            updated.remember_dialog("track", Path(filename).parent)
            self._save_preferences(updated)
            self.open_file(Path(filename))

    def _on_folder_selected(self, folder: Path | None) -> None:
        self._current_folder = folder
        self._sync_actions()

    def _on_library_load_failed(self, folder: Path, message: str) -> None:
        self.status_bar.showMessage(f"Could not read {folder}: {message}", 8000)

    def open_path(self, path: Path) -> None:
        """Add a folder as an album, or open a file through the normal analysis pipeline."""
        try:
            path = path.expanduser().absolute()
            if path.is_dir():
                self.library_panel.add_album(path)
                return
        except (OSError, ValueError) as error:
            self.status_bar.showMessage(f"Could not open {path}: {error}", 10000)
            return
        self.open_file(path)

    @staticmethod
    def _can_copy_urls(event: QDropEvent) -> bool:
        # Ignore our own sample drags: their WAVs are temporary, not library sources.
        return (
            event.source() is None
            and bool(event.possibleActions() & Qt.DropAction.CopyAction)
            and event.mimeData().hasUrls()
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self.dragMoveEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._can_copy_urls(event):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if not self._can_copy_urls(event):
            event.ignore()
            return
        accepted = set()
        unsupported = 0
        # Moving an already-listed nested track to the session list must not select a track.
        with QSignalBlocker(self.library_panel):
            for url in event.mimeData().urls():
                if not url.isLocalFile() or url.host() not in {"", "localhost"}:
                    unsupported += 1
                    continue
                path = Path(url.path() if url.host() else url.toLocalFile())
                if path in accepted:
                    continue
                try:
                    if not path.is_absolute():
                        unsupported += 1
                        continue
                    if path.is_dir():
                        self.library_panel.add_dropped_path(path, is_album=True)
                    elif path.suffix.lower() in audio_io.AUDIO_EXTENSIONS and path.is_file():
                        self.library_panel.add_dropped_path(path, is_album=False)
                    else:
                        unsupported += 1
                        continue
                except (OSError, ValueError):
                    unsupported += 1
                    continue
                accepted.add(path)
        if unsupported:
            self.status_bar.showMessage(
                f"Skipped {unsupported} unsupported or unavailable drop item(s).", 8000
            )
        if accepted:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    # --- analyse d'une piste ---------------------------------------------

    def open_file(self, path: Path, *, chop: ChopOptions | None = None) -> None:
        """Open an external file through the normal library-selection pipeline."""
        try:
            path = path.expanduser().absolute()
            if not path.is_file():
                raise FileNotFoundError("File does not exist or is not a regular file.")
            # Check readability without decoding or changing the source audio.
            with path.open("rb"):
                pass
            if chop is None:
                self._start_track_analysis(path, external=True)
            else:
                self._start_track_analysis(path, external=True, chop=chop)
        except (OSError, ValueError, audio_io.AudioLoadError) as error:
            self.status_bar.showMessage(f"Could not open {path}: {error}", 10000)

    def _on_track_selected(self, path: Path) -> None:
        self._start_track_analysis(path)

    def _start_track_analysis(
        self, path: Path, *, external: bool = False, chop: ChopOptions | None = None
    ) -> None:
        if self._is_analysis_running():
            # Une analyse (piste ou album) est déjà en cours : la bibliothèque est
            # désactivée pendant ce temps (voir _set_busy), donc ce cas ne devrait
            # arriver que par un appel programmatique. Deux QThread simultanés sur
            # le même MainWindow ont déjà fait planter l'appli en pratique (le
            # second écrase la seule référence Python vers le premier, encore en
            # cours) : on refuse plutôt que de risquer ça.
            self.status_bar.showMessage("Analysis is already running. Please wait.", 4000)
            return

        if not self.selection_controller.authorize_transition("track", include_region=True):
            return
        track = audio_io.read_track(path)
        self._opening_external_track = external
        if external:
            self.library_panel.clearSelection()
            self._current_folder = None
        self.selection_controller.reset()
        self.sample_state.clear()
        self.track_label.clear()
        self.waveform_view.clear()
        self._current_track = track
        self.status_bar.showMessage(f"Analyzing {track.title}…")

        worker = (
            TrackAnalysisWorker(track, self.settings, self.cache)
            if chop is None
            else TrackAnalysisWorker(track, self.settings, self.cache, chop=chop)
        )
        worker.finished.connect(self._on_track_analyzed)
        worker.failed.connect(self._on_track_failed)
        self._set_busy(True)
        self._run_worker(worker)

    def _on_track_analyzed(self, result: LoadedTrack) -> None:
        if self._closing:
            return
        self.selection_controller.reset()
        self._set_busy(False)
        analysis = result.analysis
        if self._opening_external_track:
            self._opening_external_track = False
            self.library_panel.add_track(analysis.track.path)
        samples, sample_rate = result.samples, result.sample_rate
        candidates = list(result.candidates)

        self.waveform_view.set_waveform(samples, sample_rate)
        self.waveform_view.set_downbeats(analysis.downbeat_times)
        self.sample_state.load_track(result)
        self._sync_selection()
        self.track_label.setText(f"{analysis.track.title} — {analysis.tempo_bpm:.1f} BPM")

        sample_word = "sample" if len(candidates) == 1 else "samples"
        self.status_bar.showMessage(
            f"{analysis.track.title} — {analysis.tempo_bpm:.1f} BPM, {len(candidates)} {sample_word}",
            5000,
        )
        worker = self.sender()
        if (
            isinstance(worker, TrackAnalysisWorker)
            and worker.chop is not None
            and worker.chop.export_dir is not None
            and result.candidates
        ):
            self._export_candidates(result.candidates, destination=worker.chop.export_dir)

    def _on_track_failed(self, message: str) -> None:
        self._opening_external_track = False
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

        if not self.selection_controller.authorize_transition("album", include_region=True):
            return
        self.sample_state.stop()

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

    def _save_preferences(self, updated: Settings) -> None:
        save_settings(updated, previous=self.settings)
        self.settings = updated

    def _on_settings_clicked(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        palette = self.theme_manager.palette
        dialog.setPalette(palette.to_qpalette())
        palette.apply_control_styles(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_preferences(dialog.settings())
            with QSignalBlocker(self.auto_play_checkbox):
                self.auto_play_checkbox.setChecked(self.settings.auto_play)
            self.sample_state.set_auto_play(self.settings.auto_play)
            self.theme_manager.set_force_dark(self.settings.force_dark)

    def _apply_theme(self) -> None:
        palette = self.theme_manager.palette
        self.setPalette(palette.to_qpalette())
        for dialog in self.findChildren(SettingsDialog):
            dialog.setPalette(palette.to_qpalette())
        palette.apply_control_styles(self)
        self.waveform_view.apply_theme(palette)
        self.sample_lanes.apply_theme(palette)
        self.candidates_panel.apply_theme(palette)

    # --- préécoute -------------------------------------------------------

    def _mark_active_sample(self) -> None:
        if self.sample_state.active_id is not None:
            self.sample_state.toggle_mark(self.sample_state.active_id)

    def _sync_actions(self) -> None:
        state = self.sample_state
        controller = self.selection_controller
        locked = controller.locked or self._analysis_busy or self._thread is not None
        available = {
            "analyze_album": self._current_folder is not None and not locked,
            "settings": not locked,
            "open_library": not locked,
            "add_album": not locked,
            "open_track": not locked,
            "play": state.can_preview and not locked,
            "stop": state.has_playback
            or controller.window is not None
            or controller.result_window is not None,
            "chop_selection": controller.window is not None and state.loaded_track is not None and not locked,
            "whole_track": (controller.window is not None or controller.result_window is not None)
            and not locked,
            "mark": state.active_id is not None and not locked,
            "mark_all": bool(state.items) and not locked,
            "clear_marks": bool(state.marked_ids) and not locked,
            "export_marked": bool(state.marked_ids) and not locked,
            "export_all": bool(state.items) and not locked,
        }
        for name, enabled in available.items():
            self.action_registry.set_available(name, enabled)

    def _on_preview_failed(self, message: str) -> None:
        self.status_bar.showMessage(message, 8000)

    def _on_auto_play_toggled(self, enabled: bool) -> None:
        self.sample_state.set_auto_play(enabled)
        self._save_preferences(replace(self.settings, auto_play=enabled))

    def _play_sample(self, item_id: int, token: int) -> None:
        loaded = self.sample_state.loaded_track
        if loaded is not None:
            item = next(item for item in self.sample_state.items if item.id == item_id)
            self.preview_player.play(loaded.samples, loaded.sample_rate, item.candidate, token)

    def _play_range(self, window: Window, token: int) -> None:
        loaded = self.sample_state.loaded_track
        if loaded is not None:
            candidate = Candidate(CandidateType.ONE_SHOT, window[0], window[1], 0.0)
            self.preview_player.play(loaded.samples, loaded.sample_rate, candidate, token)

    def _sync_playback_highlight(self) -> None:
        candidate = next(
            (item.candidate for item in self.sample_state.items if item.id == self.sample_state.playing_id),
            None,
        )
        window = self.sample_state.playing_window
        if window is not None:
            candidate = Candidate(CandidateType.ONE_SHOT, window[0], window[1], 0.0)
        self.waveform_view.set_playing_candidate(candidate)

    def _stop_or_leave_selection(self) -> None:
        self.sample_state.stop()
        self.selection_controller.request_whole_track()

    def _sync_selection(self) -> None:
        controller = self.selection_controller
        loaded = self.sample_state.loaded_track
        locked = controller.locked or self._analysis_busy or self._thread is not None
        self.length_combo.setEnabled(loaded is not None and not locked)
        self.candidates_panel.setEnabled(not locked)
        self.sample_lanes.setEnabled(not locked)
        index = self.length_combo.findData(controller.length_bars)
        self.length_combo.blockSignals(True)
        self.length_combo.setCurrentIndex(index)
        self.length_combo.blockSignals(False)
        self.waveform_view.set_selection_enabled(loaded is not None and not locked)
        if self.waveform_view.selection != controller.window:
            self.waveform_view.set_selection(controller.window)
        text = "Whole track"
        if controller.window is not None:
            text = "Selection: " + " - ".join(format_time(t) for t in controller.window)
        if controller.result_window is not None:
            text += " | Samples from: " + " - ".join(format_time(t) for t in controller.result_window)
        self.selection_label.setText(text)
        self.selection_status_label.setText(controller.status_message)
        self._sync_actions()

    def _start_candidate_search(self, request_id: int, window: Window | None, length: float | None) -> None:
        loaded = self.sample_state.loaded_track
        if self._is_analysis_running() or loaded is None:
            self.selection_controller.fail(request_id, "Another task is still finishing. Please wait.")
            return
        self._search_request_id = request_id
        worker = CandidateSearchWorker(request_id, loaded, self.settings, window=window, length_bars=length)
        worker.finished.connect(self._on_candidate_search_finished)
        worker.failed.connect(self._on_candidate_search_failed)
        self._run_worker(worker)
        self._sync_selection()
        self.library_panel.setEnabled(False)

    @Slot(object)
    def _on_candidate_search_finished(self, result: CandidateSearchResult) -> None:
        if not self._closing and self.selection_controller.apply_result(result):
            self.status_bar.showMessage(result.message, 8000)

    @Slot(str)
    def _on_candidate_search_failed(self, message: str) -> None:
        worker = self.sender()
        if (
            isinstance(worker, CandidateSearchWorker)
            and not self._closing
            and self.selection_controller.fail(worker.request_id, message)
        ):
            self.status_bar.showMessage(self.selection_controller.status_message, 8000)

    # --- export -------------------------------------------------------

    def _sample_edit_blocked(self) -> bool:
        return (
            self._closing
            or self._analysis_busy
            or self._is_analysis_running()
            or self.selection_controller.locked
        )

    def _edit_sample_bpm(self, item_id: int) -> None:
        if self._sample_edit_blocked():
            return
        item = next((item for item in self.sample_state.items if item.id == item_id), None)
        if item is None:
            return
        result = choose_bpm(
            self, item.candidate.bpm, self.sample_state.sample_source_bpm(item_id), self.theme_manager.palette
        )
        if result is None or self._sample_edit_blocked():
            return
        bpm, change_speed = result
        try:
            self.sample_state.set_bpm(item_id, bpm, change_speed=change_speed)
        except ValueError as error:
            self.status_bar.showMessage(str(error), 8000)

    def _edit_sample_boundary(self, item_id: int, boundary: Literal["start", "end"]) -> None:
        if (
            self._closing
            or self._analysis_busy
            or self._is_analysis_running()
            or self.selection_controller.locked
        ):
            return
        item = next((item for item in self.sample_state.items if item.id == item_id), None)
        if item is None:
            return
        offset = item.start_offset_ms if boundary == "start" else item.end_offset_ms
        title = "Start offset" if boundary == "start" else "End offset"
        text, accepted = QInputDialog.getText(self, title, f"{title} (ms):", text=str(offset))
        if (
            not accepted
            or self._closing
            or self._analysis_busy
            or self._is_analysis_running()
            or self.selection_controller.locked
        ):
            return
        value = text.strip()
        try:
            if not re.fullmatch(r"[+-]?[0-9]+", value):
                raise ValueError
            offset = int(value)
        except ValueError:
            self.status_bar.showMessage("Enter a whole number of milliseconds.", 8000)
            return
        try:
            self.sample_state.set_boundary_offset(item_id, boundary, offset)
        except ValueError as error:
            self.status_bar.showMessage(str(error), 8000)

    def _ensure_export_directory(self) -> Path | None:
        if self.settings.export_dir:
            return Path(self.settings.export_dir)
        directory = choose_export_folder(self, self.settings.dialog_start("export"))
        if directory is None:
            return None
        updated = replace(self.settings, export_dir=str(directory))
        updated.remember_dialog("export", directory)
        try:
            self._save_preferences(updated)
        except Exception as exc:  # noqa: BLE001 - report persistence failures before writing any audio
            self.status_bar.showMessage(f"Could not save the sample folder: {exc}", 10000)
            return None
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

        self._export_candidates(candidates)

    def _export_manual_candidates(self) -> bool:
        if self.selection_controller.result_window is None:
            return False
        return self._export_candidates(tuple(item.candidate for item in self.sample_state.items))

    def _on_sample_export_requested(self, item_id: int) -> None:
        if (
            self._closing
            or self._analysis_busy
            or self._is_analysis_running()
            or self.selection_controller.locked
        ):
            return
        item = next((item for item in self.sample_state.items if item.id == item_id), None)
        if item is not None:
            self._export_candidates((item.candidate,))

    def _export_candidates(
        self, candidates: tuple[Candidate, ...], *, destination: Path | None = None
    ) -> bool:
        loaded = self.sample_state.loaded_track
        if loaded is None or not candidates:
            return False
        self.sample_state.stop()

        directory = destination if destination is not None else self._ensure_export_directory()
        if directory is None:
            return False

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
            return False
        else:
            self.status_bar.setToolTip("")
            self.status_bar.showMessage(f"Exported {len(report.paths)} {file_word}", 5000)
            return len(report.paths) == len(candidates)

    def _on_drag_requested(self, item_id: int) -> None:
        loaded = self.sample_state.loaded_track
        item = next((item for item in self.sample_state.items if item.id == item_id), None)
        if loaded is None or item is None:
            return
        # Preserve legacy drag playback outside manual mode.
        if (
            self.selection_controller.window is not None
            or self.selection_controller.result_window is not None
        ):
            self.sample_state.stop()
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
        return self._thread is not None

    def _set_busy(self, busy: bool) -> None:
        """Empêche de lancer une deuxième analyse pendant qu'une autre tourne déjà :
        deux QThread simultanés sur cette fenêtre se sont déjà marché dessus en
        pratique (voir _run_worker)."""
        self._analysis_busy = busy
        self.library_panel.setEnabled(not busy)
        self.analyze_album_button.setEnabled(not busy and self._current_folder is not None)
        self.action_registry.set_available("analyze_album", not busy and self._current_folder is not None)
        self._sync_selection()

    def _run_worker(self, worker: TrackAnalysisWorker | AlbumAnalysisWorker | CandidateSearchWorker) -> None:
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
        self._search_request_id = None
        self.library_panel.setEnabled(not self._analysis_busy)
        self._sync_selection()

    def closeEvent(self, event) -> None:
        if self._closing or not self.selection_controller.authorize_transition("close", include_region=True):
            event.ignore()
            return
        self._closing = True
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
            if not self._thread.wait(30_000):
                self._closing = False
                if self._search_request_id is not None:
                    self.selection_controller.fail(
                        self._search_request_id, "Task still running; close again when it finishes."
                    )
                self.status_bar.showMessage("Task still running. Chopper remains open; please wait.", 10000)
                event.ignore()
                return
        self.selection_controller.reset()
        self.cache.close()
        super().closeEvent(event)
