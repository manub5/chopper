from dataclasses import replace

import pytest

from chopper.core.settings import Settings
from chopper.gui.presentation import CandidateSearchResult
from chopper.gui.sample_state import SampleState
from chopper.gui.workers import search_candidates


def setup_controller(loaded_track):
    from chopper.gui.selection_controller import SelectionController
    from chopper.gui.selection_dialog import SelectionDecision

    state = SampleState(auto_play=False)
    state.load_track(loaded_track)
    policy = {"decision": SelectionDecision.DISCARD, "export_ok": True}
    choices, exports, requests = [], [], []

    def choose(action, can_export):
        choices.append((action, can_export))
        return policy["decision"]

    def export_all():
        exports.append(tuple(item.candidate for item in state.items))
        return policy["export_ok"]

    controller = SelectionController(state, choose=choose, export_all=export_all)
    controller.search_requested.connect(lambda *args: requests.append(args))
    return controller, state, policy, choices, exports, requests


def result_for(state, request):
    request_id, window, length = request
    loaded = state.loaded_track
    candidates, message = search_candidates(
        loaded, Settings(candidates_per_track=2), window=window, length_bars=length
    )
    return CandidateSearchResult(request_id, replace(loaded, candidates=candidates), window, length, message)


def with_results(loaded_track):
    context = setup_controller(loaded_track)
    controller, state, _, _, _, requests = context
    controller.set_selection((0.0, 3.0))
    assert controller.request_chop()
    assert controller.apply_result(result_for(state, requests[-1]))
    state.mark_all()
    return context


@pytest.mark.parametrize("failed_export", [False, True])
def test_cancel_or_failed_export_preserves_region_results_marks(qapp, loaded_track, failed_export):
    from chopper.gui.selection_dialog import SelectionDecision

    controller, state, policy, choices, exports, requests = with_results(loaded_track)
    old_items, marks, loaded = state.items, state.marked_ids, state.loaded_track
    policy["decision"] = SelectionDecision.EXPORT if failed_export else SelectionDecision.CANCEL
    policy["export_ok"] = False
    assert not controller.request_whole_track()
    assert controller.window == controller.result_window == (0.0, 3.0)
    assert state.items is old_items and state.loaded_track is loaded and state.marked_ids == marks
    assert not controller.busy and len(requests) == 1
    assert choices[-1][1] is True and len(exports) == int(failed_export)


def test_cancel_retains_region_even_before_first_chop(qapp, loaded_track):
    from chopper.gui.selection_dialog import SelectionDecision

    controller, _state, policy, choices, exports, requests = setup_controller(loaded_track)
    policy["decision"] = SelectionDecision.CANCEL
    controller.set_selection((0.2, 0.8))
    assert not controller.request_whole_track()
    assert controller.window == (0.2, 0.8) and not controller.busy
    assert choices[-1][1] is False and not exports and not requests


def test_discard_only_authorizes_until_search_succeeds(qapp, loaded_track):
    controller, state, _, _, _, requests = with_results(loaded_track)
    old_items, marks = state.items, state.marked_ids
    assert controller.request_whole_track()
    assert controller.busy and controller.window == (0.0, 3.0)
    assert state.items is old_items and state.marked_ids == marks
    request = requests[-1]
    assert request[1:] == (None, None)
    assert controller.fail(request[0], "disk unavailable")
    assert not controller.busy and state.items is old_items and state.marked_ids == marks
    assert "disk unavailable" in controller.status_message
    assert controller.request_whole_track()
    assert controller.apply_result(result_for(state, requests[-1]))
    assert controller.window is controller.result_window is None
    assert not state.marked_ids and not controller.busy


def test_empty_results_still_confirm_but_cannot_export(qapp, loaded_track):
    from chopper.gui.selection_dialog import SelectionDecision

    controller, state, policy, choices, exports, requests = setup_controller(loaded_track)
    controller.set_selection((0.2, 0.8))
    controller.set_length(4.0)
    assert controller.apply_result(result_for(state, requests[-1]))
    assert state.items == () and controller.result_window == (0.2, 0.8)
    policy["decision"] = SelectionDecision.CANCEL
    assert not controller.request_whole_track() and choices[-1][1] is False
    assert not controller.authorize_transition("close")
    assert not exports


def test_length_change_rechops_current_selection_and_preserves_results_on_failure(qapp, loaded_track):
    controller, state, _, _, _, requests = with_results(loaded_track)
    old_items, marks = state.items, state.marked_ids
    controller.set_selection((0.2, 0.8))
    assert len(requests) == 1
    controller.set_length(4.0)
    assert controller.result_window == (0.0, 3.0) and controller.result_length_bars == 1.0
    assert controller.window == (0.2, 0.8) and controller.length_bars == 4.0
    assert state.items is old_items and state.marked_ids == marks
    assert len(requests) == 2 and requests[-1][1:] == ((0.2, 0.8), 4.0)
    assert controller.fail(requests[-1][0], "search failed")
    assert state.items is old_items and state.marked_ids == marks
    controller.set_length(4.0)
    assert len(requests) == 2


def test_length_without_selection_only_sets_next_length(qapp, loaded_track):
    controller, _, _, _, _, requests = setup_controller(loaded_track)
    controller.set_length(2.0)
    assert controller.length_bars == 2.0 and not requests


def test_second_chop_replaces_results_without_confirmation(qapp, loaded_track):
    from chopper.gui.selection_dialog import SelectionDecision

    controller, state, policy, choices, exports, requests = with_results(loaded_track)
    policy["decision"] = SelectionDecision.CANCEL
    old_items = state.items
    assert controller.request_chop()
    assert len(requests) == 2 and not choices and not exports
    assert state.items is old_items
    assert controller.apply_result(result_for(state, requests[-1]))
    assert state.items is not old_items


@pytest.mark.parametrize("mismatch", ["id", "window", "length", "audio", "analysis", "rate"])
def test_stale_result_cannot_replace_new_generation(qapp, loaded_track, mismatch):
    controller, state, _, _, _, requests = setup_controller(loaded_track)
    controller.set_selection((0.0, 3.0))
    controller.request_chop()
    old = result_for(state, requests[-1])
    controller.reset()
    controller.set_selection((0.0, 3.0))
    controller.request_chop()
    current = result_for(state, requests[-1])
    wrong = {
        "id": replace(current, request_id=old.request_id),
        "window": replace(current, window=(0.0, 2.0)),
        "length": replace(current, length_bars=2.0),
        "audio": replace(current, loaded=replace(current.loaded, samples=current.loaded.samples.copy())),
        "analysis": replace(
            current, loaded=replace(current.loaded, analysis=replace(current.loaded.analysis))
        ),
        "rate": replace(current, loaded=replace(current.loaded, sample_rate=2000)),
    }[mismatch]
    items = state.items
    assert not controller.apply_result(wrong)
    assert state.items is items and controller.busy
    assert not controller.fail(old.request_id, "obsolete") and controller.busy
    assert controller.apply_result(current) and not controller.busy


def test_busy_blocks_changes_and_additional_requests(qapp, loaded_track):
    controller, _state, _, choices, _, requests = setup_controller(loaded_track)
    controller.set_selection((0.0, 3.0))
    controller.request_chop()
    controller.set_selection((0.2, 0.8))
    controller.set_length(4.0)
    assert not controller.request_chop() and not controller.request_whole_track()
    assert controller.window == (0.0, 3.0) and controller.length_bars == 1.0
    assert len(requests) == 1 and not choices


def test_confirmation_is_reentrant_safe_and_stops_audio_before_choice(qapp, loaded_track):
    from chopper.gui.selection_dialog import SelectionDecision

    controller, state, _, _, _, _ = with_results(loaded_track)
    observed = []

    def choose(action, can_export):
        observed.append((state.has_playback, controller.authorize_transition("close")))
        return SelectionDecision.CANCEL

    # These are the documented boundary callbacks, not replacements for the engine.
    from chopper.gui.selection_controller import SelectionController

    controller = SelectionController(state, choose=choose, export_all=lambda: True)
    controller.set_selection((0.0, 3.0))
    state.toggle_playback()
    assert state.has_playback
    assert not controller.authorize_transition("close", include_region=True)
    assert observed == [(False, False)] and not state.has_playback


def test_controller_selection_requests_range_but_length_and_ui_reset_do_not(qapp, loaded_track):
    controller, state, _, _, _, _ = setup_controller(loaded_track)
    requests = []
    state.range_play_requested.connect(lambda *args: requests.append(args))
    state.set_auto_play(True)
    controller.set_selection((0.2, 0.8))
    assert len(requests) == 1 and requests[0][0] == (0.2, 0.8)
    controller.set_length(2.0)
    controller.reset()
    assert len(requests) == 1 and not state.has_playback
    assert controller.window is controller.result_window is None
    assert controller.length_bars == 2.0
