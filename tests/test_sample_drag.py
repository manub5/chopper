from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from choppeur.gui.candidates_panel import CandidatesPanel
from choppeur.gui.sample_state import SampleState


def move_held(table, point, *, held=True):
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(point),
        QPointF(table.viewport().mapToGlobal(point)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(table.viewport(), event)


@pytest.fixture
def panel(qapp, loaded_track):
    state = SampleState(auto_play=True)
    state.load_track(loaded_track)
    panel = CandidatesPanel(state)
    panel.set_drag_enabled(True)
    panel.resize(800, 250)
    panel.show()
    qapp.processEvents()
    yield panel
    panel.close()


@pytest.mark.parametrize("action", [Qt.DropAction.CopyAction, Qt.DropAction.IgnoreAction])
@pytest.mark.parametrize("relative", [False, True])
def test_native_drag_provides_existing_absolute_url_copy_only_and_keeps_file(
    qapp, tmp_path, monkeypatch, action, relative
):
    from choppeur.gui.sample_drag import start_file_drag

    path = tmp_path / "glissés" / "sample.wav"
    path.parent.mkdir()
    path.write_bytes(b"WAV already written")
    received = []

    def platform_exec(drag, supported, default):
        urls = drag.mimeData().urls()
        assert len(urls) == 1 and urls[0].isLocalFile()
        local = Path(urls[0].toLocalFile())
        assert local == path.resolve() and local.is_file()
        assert supported == default == Qt.DropAction.CopyAction
        received.append(local)
        return action

    monkeypatch.setattr(QDrag, "exec", platform_exec)
    source = QWidget()
    monkeypatch.chdir(tmp_path)
    assert start_file_drag(source, path.relative_to(tmp_path) if relative else path) == action
    assert received == [path]
    source.close()
    assert path.read_bytes() == b"WAV already written"


def test_no_drag_with_nonexistent_file(qapp, tmp_path, monkeypatch):
    from choppeur.gui.sample_drag import start_file_drag

    calls = []
    monkeypatch.setattr(QDrag, "exec", lambda *args: calls.append(True))
    source = QWidget()
    with pytest.raises(OSError):
        start_file_drag(source, tmp_path / "missing.wav")
    assert calls == []
    source.close()


def test_only_handle_with_left_button_past_threshold_requests_drag(panel):
    table = panel.table
    state = panel.state
    requests = []
    plays = []
    panel.drag_requested.connect(requests.append)
    state.play_requested.connect(lambda *args: plays.append(args))
    point = table.visualItemRect(table.item(1, 4)).center()
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert requests == []
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    move_held(table, point + QPoint(1, 0))
    assert requests == []
    move_held(table, point + QPoint(QApplication.startDragDistance() + 2, 0), held=False)
    assert requests == []
    move_held(table, point + QPoint(QApplication.startDragDistance() + 2, 0))
    move_held(table, point + QPoint(QApplication.startDragDistance() + 4, 0))
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert requests == [state.items[1].id]
    assert state.active_id is None and not state.marked_ids and plays == []


def test_other_columns_never_start_file_drag(panel):
    table = panel.table
    requests = []
    panel.state.set_auto_play(False)
    panel.drag_requested.connect(requests.append)
    point = table.visualItemRect(table.item(0, 1)).center()
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    move_held(table, point + QPoint(40, 0))
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert requests == []


def test_right_click_on_handle_neither_selects_nor_starts_drag(panel):
    state = panel.state
    state.navigate(state.items[0].id)
    requests = []
    panel.drag_requested.connect(requests.append)
    point = panel.table.visualItemRect(panel.table.item(1, 4)).center()
    QTest.mouseClick(panel.table.viewport(), Qt.MouseButton.RightButton, pos=point)
    assert state.active_id == state.items[0].id
    assert not state.marked_ids and requests == []


def test_explicitly_disabled_handle_never_requests_drag(panel):
    panel.set_drag_enabled(False)
    table = panel.table
    requests = []
    panel.drag_requested.connect(requests.append)
    assert not table.item(0, 4).flags() & Qt.ItemFlag.ItemIsEnabled
    point = table.visualItemRect(table.item(0, 4)).center()
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    move_held(table, point + QPoint(40, 0))
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert requests == []
    assert panel.state.active_id is None


def test_handle_available_by_default_explains_first_use(qapp, loaded_track):
    state = SampleState()
    state.load_track(loaded_track)
    panel = CandidatesPanel(state)
    try:
        handle = panel.table.item(0, 4)
        assert handle.flags() & Qt.ItemFlag.ItemIsEnabled
        assert "choose" in handle.toolTip().lower() and "folder" in handle.toolTip().lower()
    finally:
        panel.close()


def test_sorted_table_drag_uses_identity_not_row(panel):
    table = panel.table
    table.sortItems(0, Qt.SortOrder.DescendingOrder)
    item_id = table.item(0, 4).data(Qt.ItemDataRole.UserRole)
    requests = []
    panel.drag_requested.connect(requests.append)
    point = table.visualItemRect(table.item(0, 4)).center()
    QTest.mousePress(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    move_held(table, point + QPoint(40, 0))
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert requests == [item_id]
