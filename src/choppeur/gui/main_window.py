from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread
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

from choppeur.core import audio_io
from choppeur.core.cache import AnalysisCache
from choppeur.core.models import Track
from choppeur.core.settings import (
    Settings,
    default_cache_path,
    load_settings,
    save_settings,
)
from choppeur.gui.candidates_panel import CandidatesPanel
from choppeur.gui.library_panel import LibraryPanel
from choppeur.gui.presentation import LoadedTrack
from choppeur.gui.preview_player import PreviewPlayer
from choppeur.gui.sample_lanes import SampleLanesView
from choppeur.gui.sample_state import SampleState
from choppeur.gui.settings_dialog import SettingsDialog
from choppeur.gui.theme import ThemeManager
from choppeur.gui.waveform_view import WaveformView
from choppeur.gui.workers import (
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
        self.setWindowTitle("Choppeur")
        self.resize(1100, 700)

        self.settings = settings if settings is not None else load_settings()
        self.cache = cache if cache is not None else AnalysisCache(default_cache_path())

        self._current_track: Track | None = None
        self._current_folder: Path | None = None
        self._thread: QThread | None = None
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

        open_library_button = QPushButton("Ouvrir une bibliothèque…")
        open_library_button.clicked.connect(self._on_open_library_clicked)

        self.analyze_album_button = QPushButton("Analyser l'album entier")
        self.analyze_album_button.setEnabled(False)
        self.analyze_album_button.clicked.connect(self._on_analyze_album_clicked)

        settings_button = QPushButton("Paramètres…")
        settings_button.clicked.connect(self._on_settings_clicked)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(open_library_button)
        self.auto_play_checkbox = QCheckBox("Lecture auto")
        self.auto_play_checkbox.setChecked(self.settings.auto_play)
        self.auto_play_checkbox.toggled.connect(self._on_auto_play_toggled)
        top_buttons.addWidget(self.auto_play_checkbox)
        top_buttons.addWidget(self.analyze_album_button)
        top_buttons.addStretch(1)
        top_buttons.addWidget(settings_button)

        right_panel = QWidget()
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
        self.candidates_panel.export_requested.connect(self._on_export_requested)

        self.theme_manager = ThemeManager(force_dark=self.settings.force_dark, parent=self)
        self.theme_manager.changed.connect(self._apply_theme)
        self._apply_theme()

        if self.settings.library_root:
            self.library_panel.set_root(Path(self.settings.library_root))

    # --- bibliothèque ---------------------------------------------------

    def _on_open_library_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Dossier racine de la bibliothèque")
        if not directory:
            return
        self.settings.library_root = directory
        save_settings(self.settings)
        self.library_panel.set_root(Path(directory))

    def _on_folder_selected(self, folder: Path) -> None:
        self._current_folder = folder
        self.analyze_album_button.setEnabled(True)

    def _on_library_load_failed(self, folder: Path, message: str) -> None:
        self.status_bar.showMessage(f"Impossible de lire {folder} : {message}", 8000)

    # --- analyse d'une piste ---------------------------------------------

    def _on_track_selected(self, path: Path) -> None:
        if self._is_analysis_running():
            # Une analyse (piste ou album) est déjà en cours : la bibliothèque est
            # désactivée pendant ce temps (voir _set_busy), donc ce cas ne devrait
            # arriver que par un appel programmatique. Deux QThread simultanés sur
            # le même MainWindow ont déjà fait planter l'appli en pratique (le
            # second écrase la seule référence Python vers le premier, encore en
            # cours) : on refuse plutôt que de risquer ça.
            self.status_bar.showMessage("Une analyse est déjà en cours, patiente un instant.", 4000)
            return

        track = audio_io.read_track(path)
        self.sample_state.clear()
        self.track_label.clear()
        self.waveform_view.clear()
        self._current_track = track
        self.status_bar.showMessage(f"Analyse de {track.title}…")

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

        self.status_bar.showMessage(
            f"{analysis.track.title} — {analysis.tempo_bpm:.1f} BPM, {len(candidates)} candidats",
            5000,
        )

    def _on_track_failed(self, message: str) -> None:
        self._set_busy(False)
        self.status_bar.showMessage(f"Échec de l'analyse : {message}", 8000)

    # --- analyse d'un album entier ---------------------------------------

    def _on_analyze_album_clicked(self) -> None:
        if self._is_analysis_running():
            self.status_bar.showMessage("Une analyse est déjà en cours, patiente un instant.", 4000)
            return

        if self._current_folder is None:
            QMessageBox.information(self, "Choppeur", "Sélectionnez d'abord un dossier d'album.")
            return

        # Le dossier est parcouru dans le worker (voir AlbumAnalysisWorker.run), pas ici :
        # sur un dossier réseau avec des milliers de pistes, lire les tags de chacune
        # peut prendre du temps, et ça ne doit pas geler l'interface avant même que la
        # barre de progression n'apparaisse.
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indéterminée tant que le dossier n'est pas encore scanné
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Recherche des pistes de l'album…")

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
            self.status_bar.showMessage("Aucun fichier audio dans ce dossier.", 5000)
            return
        self.progress_bar.setRange(0, total)

    def _on_album_scan_failed(self, message: str) -> None:
        self.status_bar.showMessage(f"Dossier devenu inaccessible : {message}", 8000)

    def _on_album_progress(self, done: int, total: int) -> None:
        self.progress_bar.setValue(done)
        self.status_bar.showMessage(f"Analyse de l'album : {done}/{total} pistes")

    def _on_album_track_failed(self, track: Track, message: str) -> None:
        self.status_bar.showMessage(f"{track.title} : échec ({message})", 8000)

    def _on_album_finished(self) -> None:
        # Si le dossier était vide, _on_album_scan_done a déjà affiché un message
        # explicite (progress_bar.maximum() est resté à 0, jamais mis à jour) :
        # ne pas l'effacer aussitôt par un "terminée" générique et peu informatif.
        had_tracks = self.progress_bar.maximum() > 0
        self._set_busy(False)
        self.progress_bar.setVisible(False)
        if had_tracks:
            self.status_bar.showMessage("Analyse de l'album terminée", 5000)

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

    def _on_export_requested(self, mode: str) -> None:
        loaded = self.sample_state.loaded_track
        if loaded is None or mode not in {"marked", "all"}:
            return
        candidates = [
            item.candidate
            for item in self.sample_state.items
            if mode == "all" or item.id in self.sample_state.marked_ids
        ]
        if not candidates:
            QMessageBox.information(self, "Choppeur", "Aucun candidat coché à exporter.")
            return

        start_dir = self.settings.export_dir or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Dossier d'export", start_dir)
        if not directory:
            return

        exported = audio_io.export_candidates(
            loaded.samples,
            loaded.sample_rate,
            loaded.analysis.track,
            candidates,
            Path(directory),
            file_format=self.settings.export_format,
        )
        self.status_bar.showMessage(f"{len(exported)} fichier(s) exporté(s)", 5000)

    # --- infrastructure -------------------------------------------------

    def _is_analysis_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _set_busy(self, busy: bool) -> None:
        """Empêche de lancer une deuxième analyse pendant qu'une autre tourne déjà :
        deux QThread simultanés sur cette fenêtre se sont déjà marché dessus en
        pratique (voir _run_worker)."""
        self.library_panel.setEnabled(not busy)
        self.analyze_album_button.setEnabled(not busy and self._current_folder is not None)

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
