import time
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pyqtgraph as pg
import pytest
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QVBoxLayout

from chopper.core import settings as settings_module
from chopper.core.cache import AnalysisCache
from chopper.core.models import CandidateType
from chopper.core.settings import Settings
from chopper.gui import main_window as main_module
from chopper.gui import workers


def wait_until(condition):
    deadline = time.monotonic() + 5
    while not condition():
        QApplication.processEvents()
        assert time.monotonic() < deadline, "Timed out waiting for actual worker completion"


@pytest.fixture
def ui(qapp, loaded_track, tmp_path, monkeypatch):
    samples = np.column_stack([np.linspace(-0.5, 0.5, 18000), np.linspace(0.3, -0.3, 18000)]).astype(
        np.float32
    )
    samples.setflags(write=False)
    analysis = replace(
        loaded_track.analysis,
        downbeat_times=tuple(float(t) for t in range(0, 19, 2)),
        onset_times=tuple(t + 0.1 for t in range(18)),
    )
    loaded = replace(loaded_track, samples=samples, analysis=analysis)
    policy = {"choice": "DISCARD", "choices": []}
    received, streams = [], []

    def choose(parent, action, can_export):
        from chopper.gui.selection_dialog import SelectionDecision

        policy["choices"].append((action, can_export))
        return getattr(SelectionDecision, policy["choice"])

    def play(data, rate, **kwargs):
        received.append((data.copy(), rate))
        streams.append(SimpleNamespace(active=True))

    monkeypatch.setattr(main_module, "confirm_selection_transition", choose, raising=False)
    monkeypatch.setattr(settings_module, "default_settings_path", lambda: tmp_path / "settings.toml")
    monkeypatch.setattr(sd, "play", play)
    monkeypatch.setattr(sd, "get_stream", lambda: streams[-1])
    monkeypatch.setattr(sd, "stop", lambda **kwargs: [setattr(s, "active", False) for s in streams])
    window = main_module.MainWindow(
        Settings(
            auto_play=False,
            export_dir=str(tmp_path / "exports"),
            candidates_per_track=2,
            max_one_shot_seconds=0.2,
        ),
        AnalysisCache(tmp_path / "cache.sqlite"),
    )
    window._on_track_analyzed(loaded)
    window.show()
    window.activateWindow()
    assert QTest.qWaitForWindowActive(window, 3000)
    qapp.processEvents()

    def forbidden(*args, **kwargs):
        raise AssertionError("Manual search must reuse loaded audio and analysis")

    for module, name in [
        (workers, "analyze_track"),
        (workers.audio_io, "load"),
        (workers.rhythm, "analyze_rhythm"),
        (workers.onsets, "detect_onsets"),
        (AnalysisCache, "get"),
        (AnalysisCache, "set"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    yield window, policy, received, loaded
    policy["choice"] = "DISCARD"
    if window._thread is not None:
        wait_until(lambda: window._thread is None)
    window.close()
    window.deleteLater()
    qapp.processEvents()


def mouse(view, kind, point, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.NoButton):
    QApplication.sendEvent(
        view.viewport(),
        QMouseEvent(
            kind,
            point,
            QPointF(view.viewport().mapToGlobal(point.toPoint())),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def draw(window, start=2.1, end=16.1):
    view = window.waveform_view
    first, last = [
        QPointF(view.mapFromScene(view.getViewBox().mapViewToScene(QPointF(t, 0)))) for t in (start, end)
    ]
    rate = pg.getConfigOption("mouseRateLimit")
    pg.setConfigOption("mouseRateLimit", 0)
    try:
        mouse(view, QEvent.Type.MouseMove, first)
        QApplication.processEvents()
        mouse(view, QEvent.Type.MouseButtonPress, first, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        mouse(view, QEvent.Type.MouseMove, first + (last - first) * 0.5, buttons=Qt.MouseButton.LeftButton)
        mouse(view, QEvent.Type.MouseMove, last, buttons=Qt.MouseButton.LeftButton)
        mouse(view, QEvent.Type.MouseButtonRelease, last, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
    finally:
        pg.setConfigOption("mouseRateLimit", rate)


def chop(window, length=2.0):
    window.selection_controller.set_length(length)
    if not window.selection_controller.busy:
        assert window.selection_controller.request_chop()
    assert window._thread is not None and window._worker is not None
    wait_until(lambda: window._thread is None)
    assert not window.selection_controller.busy


def test_length_combo_rechops_and_refreshes_both_views_without_dialog(ui):
    window, policy, received, loaded = ui
    policy["choice"] = "CANCEL"
    draw(window)
    window.chop_selection_button.click()
    assert window.selection_controller.busy
    wait_until(lambda: window._thread is None)
    old_items = window.sample_state.items

    window.length_combo.setCurrentIndex(window.length_combo.findData(2.0))
    assert window.selection_controller.busy
    assert window.sample_state.items is old_items
    assert not window.length_combo.isEnabled()
    wait_until(lambda: window._thread is None)

    state = window.sample_state
    assert state.loaded_track.samples is loaded.samples
    assert {i.candidate.bars for i in state.items if i.candidate.type is CandidateType.LOOP} == {2.0}
    assert len(state.items) == window.candidates_panel.table.rowCount()
    assert len(state.items) == len(window.sample_lanes._placements)
    assert not policy["choices"] and not received
    assert window.length_combo.isEnabled()


@pytest.mark.parametrize("length", [2.0, 4.0])
def test_draw_c_real_worker_updates_both_views_and_exports_original_audio(ui, tmp_path, length):
    window, policy, received, loaded = ui
    window.auto_play_checkbox.setChecked(True)
    window.selection_controller.set_length(length)
    draw(window)
    assert window.selection_controller.window == (2.0, 16.0)
    assert len(received) == 1
    np.testing.assert_array_equal(received[0][0], loaded.samples[2000:16000])
    assert received[0][1] == 1000
    view = window.waveform_view
    original_plot = view._waveform_item
    view.setXRange(1.0, 17.0, padding=0)
    before = view.viewRange()
    window.candidate_scope.setFocus()
    QApplication.processEvents()
    QTest.keyClick(window.candidate_scope, Qt.Key.Key_C)
    assert window._worker is not None
    wait_until(lambda: window._thread is None)
    state = window.sample_state
    assert view._waveform_item is original_plot and view.viewRange() == before
    assert state.loaded_track.samples is loaded.samples and state.loaded_track.analysis is loaded.analysis
    assert (
        len(state.items)
        == window.candidates_panel.table.rowCount()
        == len(window.sample_lanes._placements)
        == 4
    )
    assert {i.candidate.bars for i in state.items if i.candidate.type is CandidateType.LOOP} == {length}
    assert len(received) == 1 and not state.has_playback
    state.toggle_mark(state.items[0].id)
    # All manual results are exported, regardless of the single keep mark.
    window.selection_controller.set_selection((4.0, 12.0))
    policy["choice"] = "EXPORT"
    assert window.selection_controller.request_whole_track()
    wait_until(lambda: window._thread is None)
    files = list((tmp_path / "exports").glob("*.wav"))
    assert len(files) == 4 and sum(f"_{length:g}bars_" in p.name for p in files) == 2
    loop = next(p for p in files if f"_{length:g}bars_" in p.name and "00m02s" in p.name)
    data, rate = sf.read(loop, dtype="float32")
    assert rate == 1000 and data.shape == (int(length * 2000), 2)
    np.testing.assert_allclose(data, loaded.samples[2000 : 2000 + int(length * 2000)], atol=2e-7)
    assert window.selection_controller.window is None and view.selection is None
    assert {i.candidate.bars for i in state.items if i.candidate.type is CandidateType.LOOP} == {
        0.25,
        0.5,
        1.0,
    }


@pytest.mark.parametrize("transition", ["escape", "outside", "whole", "track", "album", "close"])
@pytest.mark.parametrize("decision", ["CANCEL", "EXPORT"])
def test_cancelled_or_failed_export_blocks_all_destructive_transitions(
    ui, tmp_path, monkeypatch, transition, decision
):
    window, policy, _, _ = ui
    draw(window)
    chop(window)
    state, controller = window.sample_state, window.selection_controller
    state.mark_all()
    old_items, marks, region = state.items, state.marked_ids, controller.window
    window.auto_play_checkbox.setChecked(True)
    state.select_range(region)
    assert state.has_playback
    policy["choice"] = decision
    monkeypatch.setattr(window, "_ensure_export_directory", lambda: None)
    window._current_folder = tmp_path
    if transition == "escape":
        window.action_registry.actions["stop"].trigger()
    elif transition == "outside":
        view = window.waveform_view
        point = QPointF(view.mapFromScene(view.getViewBox().mapViewToScene(QPointF(17.0, 0))))
        mouse(view, QEvent.Type.MouseMove, point)
        QApplication.processEvents()
        mouse(view, QEvent.Type.MouseButtonPress, point, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        mouse(view, QEvent.Type.MouseButtonRelease, point, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
    elif transition == "whole":
        controller.request_whole_track()
    elif transition == "track":
        window._on_track_selected(tmp_path / "other.wav")
    elif transition == "album":
        window._on_analyze_album_clicked()
    else:
        assert not window.close()
    assert controller.window == region and state.items is old_items and state.marked_ids == marks
    assert not state.has_playback and not controller.busy and window._thread is None
    assert len(policy["choices"]) == 1 and not list((tmp_path / "exports").glob("*.wav"))


def test_partial_export_keeps_successful_file_and_all_manual_state(ui, tmp_path, monkeypatch):
    window, policy, _, _ = ui
    draw(window)
    chop(window)
    state = window.sample_state
    state.mark_all()
    items, marks = state.items, state.marked_ids
    real_write = sf.write
    calls = []

    def disk_full(file, data, rate, **kwargs):
        calls.append(file)
        if len(calls) == 2:
            raise OSError("disk full")
        return real_write(file, data, rate, **kwargs)

    monkeypatch.setattr(sf, "write", disk_full)
    policy["choice"] = "EXPORT"
    assert not window.selection_controller.request_whole_track()
    assert state.items is items and state.marked_ids == marks
    assert window.selection_controller.window == (2.0, 16.0)
    assert len(list((tmp_path / "exports").glob("*.wav"))) == 1
    assert "Partial export" in window.status_bar.currentMessage()


def test_short_and_empty_searches_show_messages_and_remain_returnable(ui):
    window, _, _, _ = ui
    controller = window.selection_controller
    controller.set_selection((0.0, 0.6))
    chop(window, 4.0)
    assert len(window.sample_state.items) == 1
    assert "4-bar" in controller.status_message and "1 one-shot" in controller.status_message
    controller.set_selection((0.3, 0.6))
    chop(window, 4.0)
    assert not window.sample_state.items and "No samples" in controller.status_message
    assert window.action_registry.actions["whole_track"].isEnabled()


def test_c_and_escape_do_not_fire_in_editors_or_modal_and_actions_are_shared(ui):
    window, policy, _, _ = ui
    controller = window.selection_controller
    controller.set_selection((2.0, 16.0))
    registry = window.action_registry
    assert registry.actions["chop_selection"] in window.chop_selection_button.actions()
    assert registry.actions["whole_track"] in window.whole_track_button.actions()
    assert "C" in window.chop_selection_button.toolTip()
    assert "Chop selection" in registry.help_text() and not registry.actions["chop_selection"].autoRepeat()
    editor = QLineEdit(window.candidate_scope)
    editor.show()
    editor.setFocus()
    QApplication.processEvents()
    QTest.keyClicks(editor, "c c")
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert editor.text() == "c c" and not policy["choices"] and window._thread is None
    dialog = QDialog(window)
    QVBoxLayout(dialog).addWidget(QLineEdit())

    def reject_modal():
        QTest.keyClick(dialog, Qt.Key.Key_C)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)

    QTimer.singleShot(0, reject_modal)
    dialog.exec()
    assert not policy["choices"] and window._thread is None
    editor.close()


@pytest.mark.parametrize("dismiss", ["escape", "close"])
def test_dialog_escape_and_close_are_cancel_with_export_disabled(qapp, dismiss):
    from chopper.gui.selection_dialog import SelectionDecision, confirm_selection_transition

    seen = []

    def escape_dialog():
        box = QApplication.activeModalWidget()
        if isinstance(box, QMessageBox):
            export_button = next(b for b in box.buttons() if b.text().startswith("Export"))
            seen.append((export_button.isEnabled(), box.defaultButton().text()))
            if dismiss == "escape":
                QTest.keyClick(box, Qt.Key.Key_Escape)
            else:
                box.close()

    QTimer.singleShot(0, escape_dialog)
    assert confirm_selection_transition(None, "whole track", False) is SelectionDecision.CANCEL
    assert seen == [(False, "Cancel")]


def test_close_wait_failure_retains_live_worker_cache_and_selection(ui, monkeypatch):
    from threading import Event

    window, _, _, _ = ui
    draw(window)
    entered, release = Event(), Event()
    real_search = workers.search_candidates

    def blocked_search(*args, **kwargs):
        entered.set()
        assert release.wait(5), "Search barrier was not released"
        return real_search(*args, **kwargs)

    monkeypatch.setattr(workers, "search_candidates", blocked_search)
    controller = window.selection_controller
    assert controller.request_chop()
    wait_until(entered.is_set)
    thread, worker = window._thread, window._worker
    monkeypatch.setattr(thread, "wait", lambda timeout: False)
    items = window.sample_state.items
    try:
        assert not window.close()
        assert window._thread is thread and window._worker is worker and thread.isRunning()
        assert window.cache._connection.execute("SELECT 1").fetchone() == (1,)
        assert controller.window == (2.0, 16.0) and window.sample_state.items is items
        assert not window.length_combo.isEnabled() and not window.chop_selection_button.isEnabled()
    finally:
        release.set()
        wait_until(lambda: window._thread is None)
    # The invalidated close-time request cannot later overwrite the old results.
    assert window.sample_state.items is items and controller.result_window is None


def test_busy_search_disables_sample_widgets_until_real_thread_finishes(ui, monkeypatch):
    from threading import Event

    window, _, _, _ = ui
    draw(window)
    release = Event()
    real_search = workers.search_candidates

    def blocked_search(*args, **kwargs):
        assert release.wait(5)
        return real_search(*args, **kwargs)

    monkeypatch.setattr(workers, "search_candidates", blocked_search)
    assert window.selection_controller.request_chop()
    try:
        assert not window.sample_lanes.isEnabled()
        assert not window.candidates_panel.table.isEnabled()
        assert not window.length_combo.isEnabled() and not window.library_panel.isEnabled()
        current = window._thread
        window._on_track_selected(window.sample_state.loaded_track.analysis.track.path)
        assert window._thread is current
    finally:
        release.set()
        wait_until(lambda: window._thread is None)
    assert window.sample_lanes.isEnabled() and window.candidates_panel.table.isEnabled()


def test_confirmation_modal_rejects_reentry_and_old_callbacks(ui, monkeypatch):
    from chopper.gui.presentation import CandidateSearchResult
    from chopper.gui.selection_dialog import SelectionDecision, confirm_selection_transition

    window, policy, _, loaded = ui
    draw(window)
    chop(window)
    state = window.sample_state
    state.mark_all()
    state.set_auto_play(True)
    state.select_range((2.0, 16.0))
    token = state._token
    items, marks = state.items, state.marked_ids
    seen = []

    def during_modal():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, QMessageBox):
            return
        seen.append(not window.close())
        seen.append(not window.selection_controller.request_whole_track())
        state.playback_finished(token)
        window._on_candidate_search_finished(CandidateSearchResult(-1, loaded, None, None, "stale"))
        QTest.keyClick(dialog, Qt.Key.Key_Escape)

    def confirm(parent, action, can_export):
        QTimer.singleShot(0, during_modal)
        return confirm_selection_transition(parent, action, can_export)

    monkeypatch.setattr(main_module, "confirm_selection_transition", confirm)
    assert not window.selection_controller.request_whole_track()
    assert seen == [True, True] and state.items is items and state.marked_ids == marks
    assert not state.has_playback and not window.selection_controller.busy
    assert not policy["choices"]
    # Restore the safe test boundary for fixture cleanup.
    monkeypatch.setattr(main_module, "confirm_selection_transition", lambda *args: SelectionDecision.DISCARD)


def test_discard_preserves_already_exported_files(ui, tmp_path):
    window, _, _, _ = ui
    draw(window)
    chop(window)
    assert window._export_candidates(tuple(item.candidate for item in window.sample_state.items))
    before = {path: path.read_bytes() for path in (tmp_path / "exports").glob("*.wav")}
    assert window.selection_controller.request_whole_track()
    wait_until(lambda: window._thread is None)
    assert before and {path: path.read_bytes() for path in (tmp_path / "exports").glob("*.wav")} == before


def test_settings_save_failure_during_confirmed_export_preserves_manual_results(ui, tmp_path, monkeypatch):
    window, policy, _, _ = ui
    draw(window)
    chop(window)
    state = window.sample_state
    state.mark_all()
    items, marks = state.items, state.marked_ids
    policy["choice"] = "EXPORT"
    window.settings.export_dir = None
    monkeypatch.setattr(main_module, "choose_export_folder", lambda parent: tmp_path / "new-exports")

    def cannot_save(settings):
        raise OSError("settings read-only")

    monkeypatch.setattr(main_module, "save_settings", cannot_save)
    assert not window.selection_controller.request_whole_track()
    assert state.items is items and state.marked_ids == marks and window.settings.export_dir is None
    assert window.selection_controller.window == (2.0, 16.0) and not (tmp_path / "new-exports").exists()


def test_real_worker_failure_updates_ui_only_on_main_thread_and_keeps_results(ui, monkeypatch):
    from PySide6.QtCore import QThread

    window, _, _, _ = ui
    draw(window)
    chop(window)
    state = window.sample_state
    state.mark_all()
    items, marks = state.items, state.marked_ids
    controller = window.selection_controller
    real_fail = controller.fail
    observed = []

    def fail(request_id, message):
        observed.append(QThread.currentThread() is QApplication.instance().thread())
        return real_fail(request_id, message)

    def search_failure(*args, **kwargs):
        raise RuntimeError("candidate scoring failed")

    monkeypatch.setattr(controller, "fail", fail)
    monkeypatch.setattr(workers.candidates_module, "find_one_shot_candidates", search_failure)
    assert controller.request_chop()
    wait_until(lambda: window._thread is None)
    assert observed == [True]
    assert state.items is items and state.marked_ids == marks
    assert "candidate scoring failed" in controller.status_message


def test_preview_completion_during_physical_drag_does_not_reset_region(ui):
    window, _, received, _ = ui
    state, view = window.sample_state, window.waveform_view
    state.set_auto_play(True)
    state.click(state.items[0].id)
    token = state._token
    rate = pg.getConfigOption("mouseRateLimit")
    pg.setConfigOption("mouseRateLimit", 0)
    points = [
        QPointF(view.mapFromScene(view.getViewBox().mapViewToScene(QPointF(t, 0)))) for t in (4.1, 8.0, 14.1)
    ]
    try:
        mouse(view, QEvent.Type.MouseMove, points[0])
        QApplication.processEvents()
        mouse(
            view,
            QEvent.Type.MouseButtonPress,
            points[0],
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
        mouse(view, QEvent.Type.MouseMove, points[1], buttons=Qt.MouseButton.LeftButton)
        state.playback_finished(token)
        mouse(view, QEvent.Type.MouseMove, points[2], buttons=Qt.MouseButton.LeftButton)
        mouse(view, QEvent.Type.MouseButtonRelease, points[2], Qt.MouseButton.LeftButton)
        QApplication.processEvents()
    finally:
        pg.setConfigOption("mouseRateLimit", rate)
    assert window.selection_controller.window == view.selection == (4.0, 14.0)
    assert len(received) == 2 and state.playing_window == (4.0, 14.0)


def test_manual_sample_drag_stops_preview_before_export(ui, tmp_path, monkeypatch):
    window, _, _, _ = ui
    draw(window)
    chop(window)
    state = window.sample_state
    state.set_auto_play(True)
    state.select_range((2.0, 16.0))
    observed = []
    monkeypatch.setattr(main_module, "start_file_drag", lambda *args: observed.append(state.has_playback))
    window._on_drag_requested(state.items[0].id)
    assert observed == [False] and not state.has_playback
    assert len(list((tmp_path / "exports" / "dragged").glob("*.wav"))) == 1


def test_collapsed_gesture_disables_chop_without_losing_existing_manual_results(ui):
    window, _, received, _ = ui
    draw(window)
    chop(window)
    items = window.sample_state.items
    draw(window, 0.1, 0.8)
    assert window.waveform_view.selection is window.selection_controller.window is None
    assert not window.chop_selection_button.isEnabled()
    assert window.selection_controller.result_window == (2.0, 16.0) and window.sample_state.items is items
    assert window.whole_track_button.isEnabled() and not received
    assert window.action_registry.actions["stop"].isEnabled()


def test_current_search_result_is_deferred_until_close_confirmation_is_cancelled(ui, monkeypatch):
    from threading import Event

    from chopper.gui.selection_dialog import SelectionDecision, confirm_selection_transition

    window, _, _, _ = ui
    draw(window)
    controller = window.selection_controller
    release = Event()
    real_search = workers.search_candidates

    def blocked_search(*args, **kwargs):
        assert release.wait(5)
        return real_search(*args, **kwargs)

    monkeypatch.setattr(workers, "search_candidates", blocked_search)
    items = window.sample_state.items
    assert controller.request_chop()
    observed = []

    def during_modal():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            release.set()
            wait_until(lambda: window._thread is None)
            observed.append((window.sample_state.items is items, controller.busy))
            QTest.keyClick(dialog, Qt.Key.Key_Escape)

    def confirm(parent, action, can_export):
        QTimer.singleShot(0, during_modal)
        return confirm_selection_transition(parent, action, can_export)

    monkeypatch.setattr(main_module, "confirm_selection_transition", confirm)
    try:
        assert not window.close()
        assert observed == [(True, True)]
        assert not controller.busy and controller.result_window == (2.0, 16.0)
        assert window.sample_state.items is not items
    finally:
        release.set()
        monkeypatch.setattr(
            main_module, "confirm_selection_transition", lambda *args: SelectionDecision.DISCARD
        )
