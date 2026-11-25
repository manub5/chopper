import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from chopper.core import settings as settings_module
from chopper.core.cache import AnalysisCache
from chopper.core.models import Analysis, Candidate, CandidateType
from chopper.core.settings import Settings, load_settings
from chopper.gui import main_window as main_window_module
from chopper.gui import workers
from chopper.gui.main_window import MainWindow

SAMPLE_RATE = 1000


def _pump_until(condition, timeout_seconds=3.0):
    from PySide6.QtCore import QCoreApplication

    deadline = time.monotonic() + timeout_seconds
    while not condition():
        QCoreApplication.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("condition non atteinte à temps")


@pytest.fixture
def make_window(tmp_path, monkeypatch):
    """Fabrique de MainWindow qui ferme proprement chaque fenêtre créée (et
    attend la fin de son éventuel QThread d'analyse) à la fin du test.
    Sans ça, un thread encore en cours à la sortie du process pytest peut
    provoquer un plantage natif au lieu d'une simple erreur Python."""
    created: list[MainWindow] = []
    monkeypatch.setattr(settings_module, "default_settings_path", lambda: tmp_path / "settings.toml")

    def confirm_folder_setup(box):
        assert box.windowTitle() == "Choose your sample folder"
        next(button for button in box.buttons() if button.text() == "Choose folder…").click()
        return box.result()

    monkeypatch.setattr(QMessageBox, "exec", confirm_folder_setup)

    def _factory(**settings_kwargs) -> MainWindow:
        settings = Settings(**settings_kwargs)
        cache = AnalysisCache(tmp_path / f"cache-{len(created)}.sqlite")
        window = MainWindow(settings=settings, cache=cache)
        created.append(window)
        return window

    yield _factory

    for window in created:
        window.close()


def _make_library(root, n_tracks=2):
    album = root / "Album"
    album.mkdir()
    paths = []
    for i in range(n_tracks):
        path = album / f"{i:02d} - Track.wav"
        sf.write(str(path), np.zeros(SAMPLE_RATE, dtype="float32"), SAMPLE_RATE, subtype="PCM_16")
        paths.append(path)
    return album, paths


def _fake_analyze_track(track, settings, cache=None):
    analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(0.0, 0.5, 1.0), downbeat_times=(0.0,))
    candidates = [Candidate(type=CandidateType.ONE_SHOT, start_seconds=0.0, end_seconds=0.1, score=1.0)]
    return analysis, candidates


def test_window_starts_with_album_analysis_disabled(qapp, make_window, tmp_path):
    window = make_window()
    assert window.windowTitle() == "Chopper"
    assert window.analyze_album_button.isEnabled() is False


def test_command_line_file_uses_normal_analysis_and_displays_waveform(
    qapp, make_window, tmp_path, monkeypatch
):
    from chopper import app as app_module

    path = tmp_path / "échantillon $ with spaces.wav"
    sf.write(path, np.linspace(-0.2, 0.2, 3000, dtype=np.float32), SAMPLE_RATE, subtype="PCM_16")
    before = path.read_bytes()
    window = make_window(auto_play=False, gpu_mode="cpu")
    monkeypatch.setattr(
        workers.rhythm,
        "analyze_rhythm",
        lambda *args, **kwargs: (120.0, (0.0, 0.5, 1.0, 1.5, 2.0, 2.5), (0.0, 2.0)),
    )
    opening = window.open_file
    progress = []

    def observe(path):
        assert window.isVisible()
        opening(path)
        progress.append(
            (window.status_bar.currentMessage(), window._analysis_busy, window.library_panel.isEnabled())
        )

    monkeypatch.setattr(window, "open_file", observe)
    monkeypatch.setattr(app_module, "build_window", lambda: window)

    def execute():
        _pump_until(lambda: progress and window._thread is None, timeout_seconds=15)
        return 0

    monkeypatch.setattr(
        app_module, "QApplication", lambda args: SimpleNamespace(arguments=lambda: args, exec=execute)
    )
    with pytest.raises(SystemExit) as stopped:
        app_module.main([str(path)])
    assert stopped.value.code == 0
    assert len(progress) == 1 and progress[0] == (f"Analyzing {path.stem}…", True, False)
    assert window.sample_state.loaded_track.analysis.track.path == path
    assert path.stem in window.track_label.text()
    assert "120.0 BPM" in window.track_label.text()
    assert not window._analysis_busy and window.library_panel.isEnabled()
    expected, _ = sf.read(path, dtype="float32")
    _, actual = window.waveform_view._waveform_item.getData()
    np.testing.assert_array_equal(actual, expected)
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["missing", "directory", "unreadable"])
def test_external_file_errors_leave_window_usable(qapp, make_window, tmp_path, monkeypatch, kind):
    path = tmp_path / "external.wav"
    if kind == "directory":
        path.mkdir()
    elif kind == "unreadable":
        path.write_bytes(b"unreadable sentinel")
        original = Path.open

        def denied(self, *args, **kwargs):
            if self == path:
                raise PermissionError("permission denied sentinel")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", denied)
    window = make_window(auto_play=False)
    window.open_file(path)
    assert "Could not open" in window.status_bar.currentMessage()
    assert str(path) in window.status_bar.currentMessage()
    if kind == "unreadable":
        assert "permission denied" in window.status_bar.currentMessage()
    assert window._thread is None and window.library_panel.isEnabled()
    assert window.sample_state.loaded_track is None


def test_corrupt_external_file_reports_worker_error_without_crashing(qapp, make_window, tmp_path):
    path = tmp_path / "corrupt.wav"
    path.write_bytes(b"not a WAV file")
    window = make_window(auto_play=False)
    window.open_file(path)
    _pump_until(lambda: window._thread is None)
    assert "Analysis failed:" in window.status_bar.currentMessage()
    assert str(path) in window.status_bar.currentMessage()
    assert not window._analysis_busy and window.library_panel.isEnabled()
    assert window.sample_state.loaded_track is None


def test_shared_layout_title_and_auto_persistence(qapp, make_window, monkeypatch, loaded_track):
    window = make_window()
    window.show()
    qapp.processEvents()
    saved = []
    monkeypatch.setattr(
        main_window_module, "save_settings", lambda settings: saved.append(settings.auto_play)
    )
    window._on_track_analyzed(loaded_track)
    assert loaded_track.analysis.track.title in window.track_label.text()
    assert "120" in window.track_label.text()
    assert window.auto_play_checkbox.isChecked()
    assert window.auto_play_checkbox.parent() is window.analyze_album_button.parent()
    assert window.auto_play_checkbox.geometry().right() < window.analyze_album_button.geometry().left()
    assert window.library_panel.geometry().left() == 0
    window.auto_play_checkbox.click()
    assert window.sample_state.auto_play is False
    assert saved == [False]


def test_sample_workspace_prioritizes_table_height(qapp, make_window, loaded_track):
    window = make_window(auto_play=False)
    window._on_track_analyzed(loaded_track)
    window.resize(1100, 1100)
    window.show()
    qapp.processEvents()
    waveform, lanes, table = (
        widget.height() for widget in (window.waveform_view, window.sample_lanes, window.candidates_panel)
    )
    total = waveform + lanes + table
    # Previously 3:1:1; halve the first share and reduce the second by one third.
    assert waveform / total == pytest.approx(0.30, abs=0.02)
    assert lanes / total == pytest.approx(2 / 15, abs=0.02)
    assert table / total == pytest.approx(17 / 30, abs=0.02)

    window.resize(600, 420)
    qapp.processEvents()
    sample_table = window.candidates_panel.table
    assert sample_table.viewport().height() >= sample_table.rowHeight(0)
    assert window.sample_lanes.verticalScrollBar().maximum() > 0
    assert sample_table.horizontalScrollBar().maximum() > 0


def test_title_and_status_show_tempo_with_one_decimal(qapp, make_window, loaded_track):
    from dataclasses import replace

    result = replace(loaded_track, analysis=replace(loaded_track.analysis, tempo_bpm=118.557))
    window = make_window()
    window._on_track_analyzed(result)
    assert "118.6 BPM" in window.track_label.text()
    assert "118.6 BPM" in window.status_bar.currentMessage()


def test_lane_and_table_clicks_share_active_and_marked_state(qapp, make_window, loaded_track):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window = make_window(auto_play=False)
    window.show()
    window._on_track_analyzed(loaded_track)
    qapp.processEvents()
    state = window.sample_state
    point = window.sample_lanes.sample_rect(state.items[1].id).center().toPoint()
    QTest.mouseClick(window.sample_lanes.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert window.candidates_panel.table.currentRow() == 1
    table = window.candidates_panel.table
    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        table.visualItemRect(table.item(0, 0)).center(),
    )
    assert state.active_id == state.items[1].id
    assert state.marked_ids == {state.items[0].id}
    assert len(window.waveform_view._downbeat_lines) == len(loaded_track.analysis.downbeat_times)


@pytest.mark.parametrize("completion", ["finish", "failure", "close", "new_track"])
def test_shared_player_transitions_stop_output_and_clear_indicator(
    qapp, make_window, monkeypatch, loaded_track, tmp_path, completion
):
    import sounddevice as sd
    from PySide6.QtCore import QTimer

    class Stream:
        active = True

    stream = Stream()

    def stop(**kwargs):
        stream.active = False

    monkeypatch.setattr(sd, "play", lambda *args, **kwargs: None)
    monkeypatch.setattr(sd, "get_stream", lambda: stream)
    monkeypatch.setattr(sd, "stop", stop)
    window = make_window()
    window._on_track_analyzed(loaded_track)
    state = window.sample_state
    state.toggle_mark(state.items[0].id)
    state.click(state.items[0].id)
    assert "▶" in window.candidates_panel.table.item(0, 0).text()
    assert window.waveform_view._playing_region.isVisible()
    if completion == "close":
        window.close()
    elif completion == "new_track":
        _, paths = _make_library(tmp_path)
        monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)
        window._on_track_selected(paths[0])
        assert not state.marked_ids
        _pump_until(lambda: window._thread is None)
    elif completion == "failure":

        class BrokenStream:
            @property
            def active(self):
                raise RuntimeError("disconnected")

        window.preview_player._stream = BrokenStream()
        _pump_until(lambda: state.playing_id is None)
        assert "disconnected" in window.status_bar.currentMessage()
    else:
        stream.active = False
        _pump_until(lambda: state.playing_id is None)
    assert not stream.active
    assert not window.preview_player.findChild(QTimer).isActive()
    assert state.playing_id is None
    if completion != "new_track":
        assert not window.waveform_view._playing_region.isVisible()
    if completion in {"finish", "failure"}:
        assert state.marked_ids
        assert "▶" not in window.candidates_panel.table.item(0, 0).text()


def test_auto_preference_survives_settings_dialog(qapp, make_window, monkeypatch):
    window = make_window(auto_play=False)
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    saved = []
    monkeypatch.setattr(
        main_window_module, "save_settings", lambda settings: saved.append(settings.auto_play)
    )
    window._on_settings_clicked()
    assert window.sample_state.auto_play is False
    assert not window.auto_play_checkbox.isChecked()
    assert saved == [False]


def test_new_analysis_clears_old_state_title_and_exports(
    qapp, make_window, monkeypatch, loaded_track, tmp_path
):
    _, paths = _make_library(tmp_path)
    window = make_window()
    window._on_track_analyzed(loaded_track)
    window.sample_state.mark_all()
    monkeypatch.setattr(workers, "analyze_track", lambda *args: (_ for _ in ()).throw(RuntimeError("failed")))
    window._on_track_selected(paths[0])
    assert window.sample_state.loaded_track is None
    assert not window.track_label.text()
    assert window.candidates_panel.table.rowCount() == 0
    _pump_until(lambda: window._thread is None)
    assert not window.candidates_panel.export_all_button.isEnabled()


@pytest.mark.parametrize("mode, expected_count", [("all", 2), ("marked", 1)])
def test_export_mode_uses_exact_state_subset(
    qapp, make_window, monkeypatch, loaded_track, tmp_path, mode, expected_count
):
    window = make_window()
    window._on_track_analyzed(loaded_track)
    state = window.sample_state
    state.navigate(state.items[0].id)
    state.toggle_mark(state.items[1].id)
    destination = tmp_path / "exports"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(destination))
    window._on_export_requested(mode)
    files = list(destination.glob("*.wav"))
    assert len(files) == expected_count
    if mode == "marked":
        data, rate = sf.read(files[0])
        assert rate == 1000
        np.testing.assert_allclose(data, loaded_track.samples[1000:1200], atol=2 / 2**24)


def test_selecting_a_folder_enables_album_analysis(qapp, make_window, tmp_path):
    album, _ = _make_library(tmp_path)
    window = make_window()
    window.library_panel.set_root(tmp_path)

    window.library_panel.topLevelItem(0).setSelected(True)

    assert window.analyze_album_button.isEnabled() is True
    assert window._current_folder == album


def test_library_load_failure_is_shown_in_status_bar(qapp, make_window, tmp_path):
    window = make_window()
    not_a_folder = tmp_path / "not_a_folder"
    not_a_folder.write_bytes(b"")

    window.library_panel.set_root(not_a_folder)

    assert "Could not read" in window.status_bar.currentMessage()


def test_selecting_a_track_runs_analysis_and_updates_panels(qapp, make_window, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._on_track_selected(paths[0])

    _pump_until(lambda: window.candidates_panel.table.rowCount() > 0)

    assert window.candidates_panel.table.rowCount() == 1
    assert window.waveform_view._waveform_item is not None


def test_gui_does_not_reload_audio_after_worker_result(qapp, make_window, monkeypatch, loaded_track):
    window = make_window()

    def unexpected_load(*args, **kwargs):
        raise AssertionError("GUI must not decode audio")

    monkeypatch.setattr(main_window_module.audio_io, "load", unexpected_load)
    window._on_track_analyzed(loaded_track)
    assert window.sample_state.loaded_track.samples is loaded_track.samples
    assert window.sample_state.loaded_track.sample_rate == 1000
    assert window.candidates_panel.table.rowCount() == 2


def test_worker_audio_stays_stereo_for_preview_and_export(qapp, make_window, monkeypatch, tmp_path):
    import sounddevice as sd

    path = tmp_path / "stereo.wav"
    samples = np.column_stack([np.full(1000, 0.25), np.full(1000, -0.5)]).astype(np.float32)
    sf.write(path, samples, 1000, subtype="FLOAT")
    before = path.read_bytes()
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)
    window = make_window()
    window._on_track_selected(path)
    _pump_until(lambda: window._thread is None)
    received = []
    monkeypatch.setattr(sd, "play", lambda data, rate, **kwargs: received.append((data.copy(), rate)))

    class Stream:
        active = True

    monkeypatch.setattr(sd, "get_stream", Stream)
    monkeypatch.setattr(sd, "stop", lambda **kwargs: None)
    state = window.sample_state
    state.toggle_mark(state.items[0].id)
    state.click(state.items[0].id)
    np.testing.assert_array_equal(received[0][0], samples[:100])
    assert received[0][1] == 1000
    destination = tmp_path / "exports"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(destination))
    window._on_export_requested("marked")
    data, rate = sf.read(next(destination.glob("*.wav")), dtype="float32")
    assert rate == 1000
    np.testing.assert_array_equal(data, samples[:100])
    assert path.read_bytes() == before


def test_second_load_failure_releases_thread_and_allows_retry(qapp, make_window, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path)

    def analyze_then_remove(track, settings, cache=None):
        result = _fake_analyze_track(track, settings, cache)
        if track.path == paths[0]:
            track.path.unlink()
        return result

    monkeypatch.setattr(workers, "analyze_track", analyze_then_remove)
    window = make_window()
    window._on_track_selected(paths[0])
    _pump_until(lambda: window._thread is None)
    assert "Analysis failed" in window.status_bar.currentMessage()
    assert window.candidates_panel.table.rowCount() == 0
    assert window.library_panel.isEnabled()
    window._on_track_selected(paths[1])
    _pump_until(lambda: window._thread is None)
    assert window.candidates_panel.table.rowCount() == 1


@pytest.mark.parametrize("error", [OSError("fichier illisible"), RuntimeError("modèle indisponible")])
def test_failed_track_analysis_releases_thread_and_allows_another_track(
    qapp, make_window, monkeypatch, tmp_path, error
):
    _, paths = _make_library(tmp_path, n_tracks=2)

    def analyze_with_failure(track, settings, cache=None):
        if track.path == paths[0]:
            raise error
        return _fake_analyze_track(track, settings, cache)

    monkeypatch.setattr(workers, "analyze_track", analyze_with_failure)
    window = make_window()
    window._on_track_selected(paths[0])

    _pump_until(lambda: "Analysis failed" in window.status_bar.currentMessage())
    assert str(error) in window.status_bar.currentMessage()
    assert window.candidates_panel.table.rowCount() == 0
    _pump_until(lambda: window._thread is None)
    assert window._worker is None
    assert window.library_panel.isEnabled()

    window._on_track_selected(paths[1])
    _pump_until(lambda: window.candidates_panel.table.rowCount() == 1)
    _pump_until(lambda: window._thread is None)
    assert window.sample_state.loaded_track is not None
    assert window.sample_state.loaded_track.analysis.track.path == paths[1]
    assert window.library_panel.isEnabled()


def test_second_track_selection_while_busy_does_not_replace_running_thread(
    qapp, make_window, monkeypatch, tmp_path
):
    """
    Reproduit un vrai plantage trouvé en revue de code : sélectionner une
    deuxième piste pendant qu'une analyse tourne déjà remplaçait la seule
    référence Python vers le QThread en cours, que Qt détruisait alors que
    le thread tournait encore (SIGABRT/SIGBUS observés en pratique).
    """
    _, paths = _make_library(tmp_path, n_tracks=2)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)
    window = make_window()

    window._on_track_selected(paths[0])
    first_thread = window._thread
    assert first_thread is not None
    assert first_thread.isRunning()

    window._on_track_selected(paths[1])  # ne doit pas remplacer le thread en cours

    assert window._thread is first_thread
    assert "already running" in window.status_bar.currentMessage()

    _pump_until(lambda: window.candidates_panel.table.rowCount() > 0)


def test_library_panel_disabled_while_a_track_analysis_runs(qapp, make_window, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)
    window = make_window()

    window._on_track_selected(paths[0])
    assert window.library_panel.isEnabled() is False

    _pump_until(lambda: window.candidates_panel.table.rowCount() > 0)
    assert window.library_panel.isEnabled() is True


def test_analyzing_an_album_reports_progress_and_reenables_button(qapp, make_window, monkeypatch, tmp_path):
    album, _paths = _make_library(tmp_path, n_tracks=2)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._current_folder = album

    window._on_analyze_album_clicked()

    _pump_until(window.analyze_album_button.isEnabled)

    assert window.progress_bar.isVisible() is False
    assert window.progress_bar.maximum() == 2


def test_analyze_album_does_not_scan_the_folder_on_the_gui_thread(qapp, make_window, monkeypatch, tmp_path):
    """
    Bug de performance trouvé en revue de code : le dossier était parcouru
    (avec lecture des tags de chaque piste) directement dans
    _on_analyze_album_clicked, avant même de démarrer le thread d'analyse.
    Sur un dossier réseau avec des milliers de pistes, ça gelait l'interface
    avant même que la barre de progression n'apparaisse. Le parcours doit
    se faire dans le thread d'arrière-plan (AlbumAnalysisWorker.run).
    """
    album, _paths = _make_library(tmp_path, n_tracks=2)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._current_folder = album

    window._on_analyze_album_clicked()

    # Juste après l'appel (avant tout traitement d'évènements), le dossier ne
    # doit pas encore avoir été scanné : la barre est indéterminée (0, 0).
    assert window.progress_bar.maximum() == 0

    _pump_until(window.analyze_album_button.isEnabled)
    assert window.progress_bar.maximum() == 2  # mis à jour une fois le scan terminé


def test_analyze_album_on_empty_folder_reports_no_audio_files(qapp, make_window, tmp_path):
    empty_album = tmp_path / "EmptyAlbum"
    empty_album.mkdir()

    window = make_window()
    window._current_folder = empty_album

    window._on_analyze_album_clicked()
    _pump_until(lambda: "No audio files" in window.status_bar.currentMessage())


def test_analyze_album_reenables_ui_when_folder_becomes_unreachable(qapp, make_window, monkeypatch, tmp_path):
    """
    Un dossier réseau qui se déconnecte juste avant le scan ne doit jamais
    laisser l'interface bloquée en "analyse en cours" pour toujours.
    """
    album = tmp_path / "Album"
    album.mkdir()

    def _boom(folder):
        raise OSError("Input/output error")

    monkeypatch.setattr(workers, "tracks_in_folder", _boom)

    window = make_window()
    window._current_folder = album

    window._on_analyze_album_clicked()
    _pump_until(window.analyze_album_button.isEnabled)

    assert "no longer available" in window.status_bar.currentMessage()
    assert window.library_panel.isEnabled() is True


def test_settings_dialog_accepted_updates_and_saves_settings(qapp, make_window, monkeypatch, tmp_path):
    window = make_window()
    new_settings = Settings(export_format="flac")

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr("chopper.gui.settings_dialog.SettingsDialog.settings", lambda self: new_settings)
    saved = []
    monkeypatch.setattr(main_window_module, "save_settings", saved.append)

    window._on_settings_clicked()

    assert window.settings == new_settings
    assert saved == [new_settings]


def test_settings_dialog_toggles_theme_without_resetting_audio_or_preferences(
    qapp, make_window, monkeypatch, loaded_track
):
    window = make_window(auto_play=False, loop_lengths_bars=(0.5,))
    window._on_track_analyzed(loaded_track)
    original_player = window.preview_player
    saved = []
    monkeypatch.setattr(main_window_module, "save_settings", saved.append)

    def accept_dark(dialog):
        dialog._force_dark.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept_dark)
    window._on_settings_clicked()
    assert saved[-1].force_dark is True
    assert window.theme_manager.palette.dark
    assert window.settings.auto_play is False
    assert window.settings.loop_lengths_bars == (0.5,)
    assert window.preview_player is original_player
    assert window.sample_state.loaded_track is loaded_track


def test_export_flow_writes_checked_candidate_to_chosen_directory(qapp, make_window, monkeypatch, tmp_path):
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window()
    window._on_track_selected(paths[0])
    _pump_until(lambda: window.candidates_panel.table.rowCount() > 0)

    window.sample_state.mark_all()

    export_dir = tmp_path / "export"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(export_dir))

    window._on_export_requested("marked")

    exported_files = list(export_dir.glob("*.wav"))
    assert len(exported_files) == 1


def test_export_respects_the_flac_format_setting(qapp, make_window, monkeypatch, tmp_path):
    """
    Bug réel trouvé en revue de code : _on_export_requested n'a jamais lu
    self.settings.export_format, donc régler "Format d'export" sur FLAC dans
    les paramètres n'avait aucun effet — l'export produisait toujours du WAV.
    """
    _, paths = _make_library(tmp_path, n_tracks=1)
    monkeypatch.setattr(workers, "analyze_track", _fake_analyze_track)

    window = make_window(export_format="flac")
    window._on_track_selected(paths[0])
    _pump_until(lambda: window.candidates_panel.table.rowCount() > 0)
    window.sample_state.mark_all()

    export_dir = tmp_path / "export"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(export_dir))

    window._on_export_requested("marked")

    assert len(list(export_dir.glob("*.flac"))) == 1
    assert list(export_dir.glob("*.wav")) == []


def test_close_event_stops_album_worker_before_closing_the_cache(qapp, make_window, monkeypatch, tmp_path):
    """
    Bug réel trouvé en revue de code : fermer la fenêtre pendant une analyse
    d'album attendait un délai fixe de 2 s puis fermait le cache SQLite sans
    égard pour le thread d'analyse encore en cours, qui plantait ensuite sur
    "Cannot operate on a closed database" pour chaque piste restante.
    """
    _, paths = _make_library(tmp_path, n_tracks=5)

    def _slow_analyze(track, settings, cache=None):
        time.sleep(0.1)
        analysis = Analysis(track=track, tempo_bpm=120.0, beat_times=(), downbeat_times=())
        return analysis, []

    monkeypatch.setattr(workers, "analyze_track", _slow_analyze)

    window = make_window()
    window._current_folder = paths[0].parent
    window._on_analyze_album_clicked()

    running_worker = window._worker
    assert isinstance(running_worker, workers.AlbumAnalysisWorker)
    failures: list[str] = []
    running_worker.track_failed.connect(lambda track, message: failures.append(message))

    window.close()  # doit attendre la fin réelle du thread, pas un délai arbitraire

    assert running_worker._stop_requested is True
    assert not any("closed database" in message for message in failures)


def test_configured_export_skips_dialog_and_uses_selected_format(
    qapp, make_window, monkeypatch, loaded_track, tmp_path
):
    destination = tmp_path / "exports"
    window = make_window(export_dir=str(destination), export_format="flac")
    window._on_track_analyzed(loaded_track)
    window.sample_state.toggle_mark(window.sample_state.items[1].id)

    def unexpected_dialog(*args, **kwargs):
        raise AssertionError("Configured export must not ask for another destination")

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", unexpected_dialog)
    assert not destination.exists()
    window._on_export_requested("marked")
    paths = list(destination.glob("*.flac"))
    assert len(paths) == 1
    assert not (destination / "glissés").exists()
    data, rate = sf.read(paths[0], dtype="float32")
    assert rate == 1000
    np.testing.assert_allclose(data, loaded_track.samples[1000:1200], atol=2 / 2**24)


def test_cancelled_export_does_not_write_or_update_settings(
    qapp, make_window, monkeypatch, loaded_track, tmp_path
):
    window = make_window()
    window._on_track_analyzed(loaded_track)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "")
    saved = []
    monkeypatch.setattr(main_window_module, "save_settings", saved.append)
    window._on_export_requested("all")
    assert window.settings.export_dir is None
    assert saved == []
    assert list(tmp_path.rglob("*.wav")) == []
    assert list(tmp_path.rglob("glissés")) == []


def test_partial_export_names_success_and_error(qapp, make_window, monkeypatch, loaded_track, tmp_path):
    destination = tmp_path / "exports"
    window = make_window(export_dir=str(destination))
    window._on_track_analyzed(loaded_track)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(destination))
    real_write = sf.write
    calls = []

    def disk_full(file, data, rate, **kwargs):
        calls.append(file)
        if len(calls) == 2:
            raise OSError("disque plein")
        real_write(file, data, rate, **kwargs)

    monkeypatch.setattr(sf, "write", disk_full)
    window._on_export_requested("all")
    paths = list(destination.glob("*.wav"))
    assert len(paths) == 1
    assert "disque plein" in window.status_bar.currentMessage()
    assert "Partial export" in window.status_bar.currentMessage()
    assert "1 file kept:" in window.status_bar.currentMessage()
    assert paths[0].name in window.status_bar.currentMessage()


@pytest.mark.parametrize("action_name", ["CopyAction", "IgnoreAction"])
def test_handle_drag_writes_durable_wav_before_qt_and_never_plays(
    qapp, make_window, monkeypatch, loaded_track, tmp_path, action_name
):
    from pathlib import Path

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QDrag
    from PySide6.QtTest import QTest

    destination = tmp_path / "exports"
    window = make_window(export_dir=str(destination), export_format="flac")
    window.show()
    window._on_track_analyzed(loaded_track)
    qapp.processEvents()
    state = window.sample_state
    plays = []
    state.play_requested.connect(lambda *args: plays.append(args))
    received = []

    def platform_exec(drag, supported, default):
        path = Path(drag.mimeData().urls()[0].toLocalFile())
        assert path.is_file()
        assert path.parent == destination / "dragged"
        assert supported == default == Qt.DropAction.CopyAction
        received.append(path)
        return getattr(Qt.DropAction, action_name)

    monkeypatch.setattr(QDrag, "exec", platform_exec)
    assert not destination.exists()
    table = window.candidates_panel.table
    QTest.mouseClick(
        table.viewport(), Qt.MouseButton.LeftButton, pos=table.visualItemRect(table.item(1, 4)).center()
    )
    assert not destination.exists()
    for _ in range(2):
        window.candidates_panel.drag_requested.emit(state.items[1].id)
    assert len(received) == 2 and received[0] != received[1]
    first_bytes = received[0].read_bytes()
    assert state.active_id is None and not state.marked_ids and plays == []
    assert str(received[-1]) in window.status_bar.currentMessage()
    assert "Bitwig" not in window.status_bar.currentMessage()
    window.close()
    assert received[0].read_bytes() == first_bytes
    data, rate = sf.read(received[1], dtype="float32")
    assert sf.info(received[1]).subtype == "PCM_24"
    assert rate == 1000 and data.shape == (200, 2)
    np.testing.assert_allclose(data, loaded_track.samples[1000:1200], atol=2 / 2**24)


def test_missing_export_dir_keeps_handle_available_for_cancelable_setup(
    qapp, make_window, monkeypatch, loaded_track, tmp_path
):
    window = make_window()
    window._on_track_analyzed(loaded_track)

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "")
    from PySide6.QtCore import Qt

    assert window.candidates_panel.table.item(0, 4).flags() & Qt.ItemFlag.ItemIsEnabled
    window.candidates_panel.drag_requested.emit(window.sample_state.items[0].id)
    assert window.settings.export_dir is None
    assert not (tmp_path / "settings.toml").exists()
    assert list(tmp_path.rglob("glissés")) == []


def test_failed_wav_write_reports_error_and_never_starts_drag(
    qapp, make_window, monkeypatch, loaded_track, tmp_path
):
    from PySide6.QtGui import QDrag

    destination = tmp_path / "exports"
    window = make_window(export_dir=str(destination))
    window._on_track_analyzed(loaded_track)
    launched = []
    monkeypatch.setattr(QDrag, "exec", lambda *args: launched.append(True))

    def disk_full(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(sf, "write", disk_full)
    window.candidates_panel.drag_requested.emit(window.sample_state.items[0].id)
    assert launched == []
    assert "disque plein" in window.status_bar.currentMessage()
    assert "Could not create drag WAV" in window.status_bar.currentMessage()
    assert list(destination.rglob("*.wav")) == []


def test_export_dir_preference_enables_handles_without_writing(
    qapp, make_window, monkeypatch, loaded_track, tmp_path
):
    from PySide6.QtCore import Qt

    window = make_window()
    window._on_track_analyzed(loaded_track)
    destination = tmp_path / "exports"
    updated = Settings(export_dir=str(destination))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr("chopper.gui.settings_dialog.SettingsDialog.settings", lambda self: updated)
    monkeypatch.setattr(main_window_module, "save_settings", lambda *args: None)
    window._on_settings_clicked()
    assert window.candidates_panel.table.item(0, 4).flags() & Qt.ItemFlag.ItemIsEnabled
    assert not destination.exists()


def test_stale_drag_identity_never_exports_another_track(qapp, make_window, loaded_track, tmp_path):
    destination = tmp_path / "exports"
    window = make_window(export_dir=str(destination))
    window._on_track_analyzed(loaded_track)
    stale_id = window.sample_state.items[0].id
    window._on_track_analyzed(loaded_track)
    window.candidates_panel.drag_requested.emit(stale_id)
    assert not destination.exists()


def test_platform_drag_failure_keeps_created_wav_and_reports_path(
    qapp, make_window, monkeypatch, loaded_track, tmp_path
):
    from PySide6.QtGui import QDrag

    destination = tmp_path / "exports"
    window = make_window(export_dir=str(destination))
    window._on_track_analyzed(loaded_track)

    def platform_error(*args):
        raise RuntimeError("transfert indisponible")

    monkeypatch.setattr(QDrag, "exec", platform_error)
    window.candidates_panel.drag_requested.emit(window.sample_state.items[0].id)
    paths = list((destination / "dragged").glob("*.wav"))
    assert len(paths) == 1
    assert str(paths[0]) in window.status_bar.currentMessage()
    assert "transfert indisponible" in window.status_bar.currentMessage()
    assert "WAV kept:" in window.status_bar.currentMessage()
    assert "drag failed:" in window.status_bar.currentMessage()


def test_first_button_export_remembers_folder_before_writing_and_reuses_it(
    qapp, make_window, loaded_track, tmp_path, monkeypatch
):
    destination = tmp_path / "Samples été"
    window = make_window(force_dark=True, auto_play=False)
    window._on_track_analyzed(loaded_track)
    picked = []
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: picked.append(True) or str(destination)
    )
    real_write = sf.write

    def write_after_settings(*args, **kwargs):
        assert load_settings(tmp_path / "settings.toml").export_dir == str(destination)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(sf, "write", write_after_settings)
    assert not (tmp_path / "settings.toml").exists()
    window._on_export_requested("all")
    assert window.settings.export_dir == str(destination)
    assert len(list(destination.glob("*.wav"))) == 2
    reloaded = load_settings(tmp_path / "settings.toml")
    assert reloaded.force_dark and not reloaded.auto_play
    window.close()
    restarted = make_window(**reloaded.to_dict())
    restarted._on_track_analyzed(loaded_track)
    restarted._on_export_requested("all")
    assert len(list(destination.glob("*.wav"))) == 4
    assert picked == [True]


@pytest.mark.parametrize("operation", ["button", "drag"])
@pytest.mark.parametrize("stage", ["explanation", "picker"])
def test_first_use_cancel_has_no_persistent_or_audio_side_effects(
    qapp, make_window, loaded_track, tmp_path, monkeypatch, operation, stage
):
    window = make_window()
    window._on_track_analyzed(loaded_track)
    state = window.sample_state
    state.navigate(state.items[0].id)
    state.toggle_mark(state.items[1].id)
    original_settings = window.settings
    if stage == "explanation":

        def cancel(box):
            next(button for button in box.buttons() if button.text() == "Cancel").click()
            return box.result()

        monkeypatch.setattr(QMessageBox, "exec", cancel)

        def unexpected_picker(*args):
            raise AssertionError("Cancel must not open picker")

        monkeypatch.setattr(QFileDialog, "getExistingDirectory", unexpected_picker)
    else:
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "")
    if operation == "button":
        window._on_export_requested("marked")
    else:
        window._on_drag_requested(state.items[1].id)
    assert window.settings is original_settings and window.settings.export_dir is None
    assert state.active_id == state.items[0].id
    assert state.marked_ids == {state.items[1].id} and state.playing_id is None
    assert not (tmp_path / "settings.toml").exists()
    assert list(tmp_path.rglob("*.wav")) == []


@pytest.mark.parametrize("operation", ["button", "drag"])
def test_first_use_failed_save_never_exports_or_starts_transfer(
    qapp, make_window, loaded_track, tmp_path, monkeypatch, operation
):
    from pathlib import Path

    from PySide6.QtGui import QDrag

    path = tmp_path / "settings.toml"
    settings_module.save_settings(Settings(auto_play=False), path)
    before = path.read_bytes()
    window = make_window(auto_play=False)
    original = window.settings
    window._on_track_analyzed(loaded_track)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path / "samples"))

    def fail_replace(*args):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "replace", fail_replace)
    transfers = []
    monkeypatch.setattr(QDrag, "exec", lambda *args: transfers.append(True))
    if operation == "button":
        window._on_export_requested("all")
    else:
        window._on_drag_requested(window.sample_state.items[0].id)
    assert window.settings is original and window.settings.export_dir is None
    assert path.read_bytes() == before
    assert not (tmp_path / "samples").exists() and transfers == []
    assert "Could not save the sample folder:" in window.status_bar.currentMessage()


def test_first_handle_gesture_sets_up_then_second_gesture_transfers_once(
    qapp, make_window, loaded_track, tmp_path, monkeypatch
):
    from pathlib import Path

    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QDrag, QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    window = make_window()
    window.show()
    window._on_track_analyzed(loaded_track)
    qapp.processEvents()
    state = window.sample_state
    state.navigate(state.items[0].id)
    state.toggle_mark(state.items[1].id)
    state.play_requested.disconnect(window._play_sample)
    state.play_requested.connect(lambda item_id, token: state.playback_started(token))
    state.toggle_playback()
    assert state.playing_id == state.items[0].id
    picked = []
    destination = tmp_path / "samples"
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: picked.append(True) or str(destination)
    )
    transfers = []

    def transfer(drag, supported, default):
        path = Path(drag.mimeData().urls()[0].toLocalFile())
        assert path.is_file()
        transfers.append(path)
        return Qt.DropAction.CopyAction

    monkeypatch.setattr(QDrag, "exec", transfer)
    table = window.candidates_panel.table
    point = table.visualItemRect(table.item(1, 4)).center()

    def move(distance):
        position = point + QPoint(distance, 0)
        event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(position),
            QPointF(table.viewport().mapToGlobal(position)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(table.viewport(), event)

    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert picked == []
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    move(1)
    assert picked == []
    move(QApplication.startDragDistance() + 2)
    move(QApplication.startDragDistance() + 4)
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert load_settings(tmp_path / "settings.toml").export_dir == str(destination)
    assert not destination.exists() and transfers == [] and picked == [True]
    assert (
        window.status_bar.currentMessage()
        == "Sample folder saved. Drag the sample again to send it to your DAW."
    )
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    move(QApplication.startDragDistance() + 2)
    move(QApplication.startDragDistance() + 4)
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert len(transfers) == 1 and len(list(destination.rglob("*.wav"))) == 1
    assert picked == [True]
    assert state.active_id == state.items[0].id and state.playing_id == state.items[0].id
    assert state.marked_ids == {state.items[1].id}


@pytest.mark.parametrize("operation", ["button", "drag"])
def test_invalid_configured_destination_reports_error_without_fallback(
    qapp, make_window, loaded_track, tmp_path, monkeypatch, operation
):
    destination = tmp_path / "not-a-directory"
    destination.write_bytes(b"keep existing content")
    window = make_window(export_dir=str(destination))
    window._on_track_analyzed(loaded_track)

    def unexpected(*args):
        raise AssertionError("No fallback picker")

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", unexpected)
    if operation == "button":
        window._on_export_requested("all")
    else:
        window._on_drag_requested(window.sample_state.items[0].id)
    assert destination.read_bytes() == b"keep existing content"
    assert window.settings.export_dir == str(destination)
    assert (
        "Export failed" in window.status_bar.currentMessage()
        or "Could not create drag WAV" in window.status_bar.currentMessage()
    )


def test_english_studio_controls_and_owned_status_messages(qapp, make_window, loaded_track, monkeypatch):
    from PySide6.QtWidgets import QPushButton

    window = make_window()
    labels = {button.text() for button in window.findChildren(QPushButton)}
    assert {"Open library…", "Analyze album", "Settings…"} <= labels
    assert window.auto_play_checkbox.text() == "Auto-preview"
    window._on_track_analyzed(loaded_track)
    assert "2 samples" in window.status_bar.currentMessage()
    assert window.waveform_view.getAxis("bottom").labelText == "Time"
    window._on_track_failed("périphérique indisponible")
    assert window.status_bar.currentMessage() == "Analysis failed: périphérique indisponible"
    window._on_album_scan_done(0)
    assert window.status_bar.currentMessage() == "No audio files in this folder."
    window._on_album_scan_failed("NAS déconnecté")
    assert window.status_bar.currentMessage() == "Folder is no longer available: NAS déconnecté"
    window._on_album_scan_done(2)
    window._on_album_progress(1, 2)
    assert window.status_bar.currentMessage() == "Analyzing album: 1/2 tracks"
    window._on_album_finished()
    assert window.status_bar.currentMessage() == "Album analysis complete"
    messages = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda parent, title, text: messages.append((title, text))
    )
    window._on_export_requested("marked")
    assert messages == [("Chopper", "No samples marked for export.")]


def test_no_startup_or_invalid_sample_setup(qapp, make_window, loaded_track, tmp_path, monkeypatch):
    def unexpected(*args):
        raise AssertionError("Setup must require an actual exportable sample")

    monkeypatch.setattr(QMessageBox, "exec", unexpected)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    window = make_window()
    window._on_export_requested("all")
    window._on_drag_requested(0)
    window._on_track_analyzed(loaded_track)
    stale_id = window.sample_state.items[0].id
    window._on_track_analyzed(loaded_track)
    window._on_drag_requested(stale_id)
    window._on_export_requested("marked")
    assert window.settings.export_dir is None
    assert not (tmp_path / "settings.toml").exists()


@pytest.mark.parametrize("count, sample_word, file_word", [(1, "sample", "file"), (2, "samples", "files")])
def test_english_analysis_and_export_counts(
    qapp, make_window, loaded_track, tmp_path, count, sample_word, file_word
):
    from dataclasses import replace

    window = make_window(export_dir=str(tmp_path / "exports"))
    window._on_track_analyzed(replace(loaded_track, candidates=loaded_track.candidates[:count]))
    assert window.status_bar.currentMessage().endswith(f"{count} {sample_word}")
    window._on_export_requested("all")
    assert window.status_bar.currentMessage() == f"Exported {count} {file_word}"
