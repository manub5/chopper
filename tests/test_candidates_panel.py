from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QHeaderView

from chopper.gui.candidates_panel import CandidatesPanel
from chopper.gui.sample_state import SampleState


def make_panel(loaded_track, auto_play=False):
    state = SampleState(auto_play=auto_play)
    state.load_track(loaded_track)
    panel = CandidatesPanel(state)
    panel.resize(800, 250)
    panel.show()
    return panel, state


def click(panel, row, column=0, control=False):
    table = panel.table
    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier if control else Qt.KeyboardModifier.NoModifier,
        table.visualItemRect(table.item(row, column)).center(),
    )


def test_table_has_seven_columns_and_initial_order(qapp, loaded_track):
    panel, state = make_panel(loaded_track)
    assert panel.table.columnCount() == 7
    assert panel.table.rowCount() == 2
    assert panel.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == state.items[0].id
    assert panel.table.item(0, 0).text() == "1-bar loop"
    assert [panel.table.horizontalHeaderItem(i).text() for i in range(4)] == [
        "Type",
        "BPM",
        "Length",
        "Position",
    ]
    assert not panel.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    panel.close()


def test_table_formats_tempo_and_times_with_millisecond_carry(qapp, loaded_track):
    candidate = replace(loaded_track.candidates[0], bpm=118.557, start_seconds=59.9996, end_seconds=121.2346)
    panel, _state = make_panel(replace(loaded_track, candidates=(candidate,)))
    assert panel.table.item(0, 1).text() == "118.6"
    assert panel.table.item(0, 2).text() == "01:01.235"
    assert panel.table.item(0, 3).text() == "01:00.000"
    panel.close()


def test_all_sample_columns_can_be_resized(qapp, loaded_track):
    panel, _ = make_panel(loaded_track)
    header = panel.table.horizontalHeader()
    try:
        for column in range(header.count()):
            assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
            initial = header.sectionSize(column)
            header.resizeSection(column, initial + 20)
            assert header.sectionSize(column) == initial + 20
            header.resizeSection(column, initial)
            assert header.sectionSize(column) == initial
        assert panel.table.visualItemRect(panel.table.item(0, 6)).width() > 0
    finally:
        panel.close()


def test_column_edge_shows_resize_cursor_only_near_boundary(qapp, loaded_track):
    panel, _ = make_panel(loaded_track)
    header = panel.table.horizontalHeader()
    target = header.viewport()
    try:
        qapp.processEvents()
        y = target.height() // 2
        edge = header.sectionViewportPosition(1) - 1
        QTest.mouseMove(target, QPoint(edge, y))
        assert target.cursor().shape() == Qt.CursorShape.SizeHorCursor
        initial = header.sectionSize(0)
        QTest.mousePress(target, Qt.MouseButton.LeftButton, pos=QPoint(edge, y))
        QTest.mouseMove(target, QPoint(edge + 32, y))
        QTest.mouseRelease(target, Qt.MouseButton.LeftButton, pos=QPoint(edge + 32, y))
        assert header.sectionSize(0) == initial + 32
        QTest.mouseMove(target, QPoint(header.sectionSize(0) // 2, y))
        assert target.cursor().shape() == Qt.CursorShape.ArrowCursor
    finally:
        panel.close()


def test_header_highlights_sections_for_selected_rows(qapp, loaded_track):
    panel, _ = make_panel(loaded_track)
    try:
        assert panel.table.horizontalHeader().highlightSections()
    finally:
        panel.close()


def test_quarter_bar_label_and_duration(qapp, loaded_track):
    candidate = replace(loaded_track.candidates[0], bars=0.25, end_seconds=0.25)
    panel, _state = make_panel(replace(loaded_track, candidates=(candidate,)))
    assert panel.table.item(0, 0).text() == "¼-bar loop"
    assert panel.table.item(0, 2).text() == "00:00.250"
    panel.close()


@pytest.mark.parametrize("bars", [None, 3, 8, True])
def test_invalid_loop_label_fails_explicitly(loaded_track, bars):
    from chopper.gui.presentation import sample_type_label

    with pytest.raises(ValueError):
        sample_type_label(replace(loaded_track.candidates[0], bars=bars))


@pytest.mark.parametrize("auto_play", [False, True])
def test_click_selects_and_optionally_requests_play(qapp, loaded_track, auto_play):
    panel, state = make_panel(loaded_track, auto_play)
    requests = []
    state.play_requested.connect(lambda item_id, token: requests.append(item_id))
    click(panel, 1)
    assert state.active_id == state.items[1].id
    assert requests == ([state.items[1].id] if auto_play else [])
    panel.close()


def test_ctrl_click_marks_without_selecting_or_playing(qapp, loaded_track):
    panel, state = make_panel(loaded_track, True)
    click(panel, 0)
    first = state.active_id
    click(panel, 1, control=True)
    assert state.active_id == first
    assert state.marked_ids == {state.items[1].id}
    assert "✓" in panel.table.item(1, 0).text()
    assert panel.table.currentRow() == 0
    click(panel, 1, control=True)
    assert not state.marked_ids
    panel.close()


def test_keyboard_navigation_does_not_play_or_mark(qapp, loaded_track):
    panel, state = make_panel(loaded_track, True)
    state.navigate(state.items[0].id)
    requests = []
    state.play_requested.connect(lambda *args: requests.append(args))
    QTest.keyClick(panel.table, Qt.Key.Key_Down)
    assert state.active_id == state.items[1].id
    assert requests == []
    assert not state.marked_ids
    panel.close()


def test_handle_does_not_select_play_or_mark(qapp, loaded_track):
    panel, state = make_panel(loaded_track, True)
    panel.table.scrollToItem(panel.table.item(1, 6))
    click(panel, 1, 6)
    assert state.active_id is None
    assert state.playing_id is None
    assert not state.marked_ids
    panel.close()


def test_sorted_duplicate_candidates_keep_distinct_ids(qapp, loaded_track):
    duplicate = loaded_track.candidates[0]
    panel, state = make_panel(
        replace(loaded_track, candidates=(duplicate, loaded_track.candidates[1], duplicate))
    )
    panel.table.sortItems(0, Qt.SortOrder.DescendingOrder)
    target = panel.table.item(2, 0).data(Qt.ItemDataRole.UserRole)
    click(panel, 2)
    click(panel, 2, control=True)
    assert state.active_id == target
    assert state.marked_ids == {target}
    assert len({panel.table.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(3)}) == 3
    panel.close()


def test_external_state_updates_selection_playing_marks_and_counts(qapp, loaded_track):
    panel, state = make_panel(loaded_track, True)
    tokens = []
    state.play_requested.connect(lambda item_id, token: tokens.append(token))
    state.click(state.items[0].id)
    state.playback_started(tokens[0])
    state.toggle_mark(state.items[1].id)
    assert panel.table.currentRow() == 0
    assert "▶" in panel.table.item(0, 0).text()
    assert "✓" not in panel.table.item(0, 0).text()
    assert "✓" in panel.table.item(1, 0).text()
    assert panel.export_marked_button.text() == "Export marked (1)"
    assert panel.export_all_button.text() == "Export all (2)"
    state.playback_finished(tokens[0])
    assert "▶" not in panel.table.item(0, 0).text()
    assert panel.table.currentRow() == 0
    state.clear()
    assert panel.table.rowCount() == 0
    assert not panel.export_all_button.isEnabled()
    panel.close()


def test_export_buttons_request_modes_not_the_active_candidate(qapp, loaded_track):
    panel, state = make_panel(loaded_track)
    state.navigate(state.items[0].id)
    state.toggle_mark(state.items[1].id)
    requests = []
    panel.export_requested.connect(requests.append)
    panel.export_marked_button.click()
    panel.export_all_button.click()
    assert requests == ["marked", "all"]
    panel.close()


@pytest.mark.parametrize(
    "bars, label",
    [
        (4.0, "4-bar loop"),
        (2.0, "2-bar loop"),
        (1.0, "1-bar loop"),
        (0.5, "½-bar loop"),
        (0.25, "¼-bar loop"),
    ],
)
def test_english_loop_labels(loaded_track, bars, label):
    from chopper.gui.presentation import sample_type_label

    assert sample_type_label(replace(loaded_track.candidates[0], bars=bars)) == label


def test_manual_long_loops_are_displayed_and_keep_ids_after_sorting(qapp, loaded_track):
    candidates = (
        replace(loaded_track.candidates[0], bars=4.0, end_seconds=8.0),
        replace(loaded_track.candidates[0], bars=2.0, end_seconds=4.0),
    )
    panel, state = make_panel(replace(loaded_track, candidates=candidates))
    try:
        panel.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        assert panel.table.item(0, 0).text() == "2-bar loop"
        assert panel.table.item(1, 0).text() == "4-bar loop"
        click(panel, 0)
        assert state.active_id == state.items[1].id
        assert not state.marked_ids and state.playing_id is None
    finally:
        panel.close()


@pytest.mark.parametrize("column", [0, 1, 2, 3])
def test_header_clicks_alternate_sort_without_changing_sample_state(qapp, loaded_track, column):
    candidates = (
        loaded_track.candidates[1],
        replace(loaded_track.candidates[0], bars=0.25, bpm=80.0, start_seconds=0.1, end_seconds=0.35),
        replace(loaded_track.candidates[0], start_seconds=2.0, end_seconds=3.0),
    )
    panel, state = make_panel(replace(loaded_track, candidates=candidates), auto_play=True)
    try:
        qapp.processEvents()
        state.navigate(state.items[2].id)
        state.toggle_mark(state.items[1].id)
        requests = []
        state.play_requested.connect(lambda *args: requests.append(args))
        header = panel.table.horizontalHeader()
        point = QPoint(
            header.sectionViewportPosition(column) + header.sectionSize(column) // 2, header.height() // 2
        )
        orders = []
        for _ in range(4):
            QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)
            orders.append(tuple(panel.table.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(3)))
        assert orders[1] == tuple(reversed(orders[0]))
        assert orders[2] == orders[0]
        assert orders[3] == orders[1]
        assert state.active_id == state.items[2].id and state.marked_ids == {state.items[1].id}
        assert not requests and state.playing_id is None
    finally:
        panel.close()
