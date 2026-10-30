from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from choppeur.gui.candidates_panel import CandidatesPanel
from choppeur.gui.sample_state import SampleState


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


def test_table_has_five_noneditable_columns_and_initial_order(qapp, loaded_track):
    panel, state = make_panel(loaded_track)
    assert panel.table.columnCount() == 5
    assert panel.table.rowCount() == 2
    assert panel.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == state.items[0].id
    assert "Boucle" in panel.table.item(0, 0).text()
    assert not panel.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    panel.close()


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
    click(panel, 1, 4)
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
    assert "(1)" in panel.export_marked_button.text()
    assert "(2)" in panel.export_all_button.text()
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
