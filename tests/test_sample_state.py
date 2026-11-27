from dataclasses import replace

import numpy as np
import pytest

from chopper.core.models import Analysis, Candidate, CandidateType, Track


def test_loaded_track_preserves_original_audio_and_equal_candidates(tmp_path):
    from chopper.gui.presentation import LoadedTrack

    samples = np.column_stack([np.full(3000, 0.2), np.full(3000, -0.4)]).astype(np.float32)
    track = Track(tmp_path / "source.wav", "Artist", "Album", "Title", 1, 3.0, 1000)
    analysis = Analysis(track, 120, (), ())
    candidate = Candidate(CandidateType.ONE_SHOT, 1, 1.2, 0.5)
    loaded = LoadedTrack(analysis, (candidate, candidate), samples, 1000)
    assert loaded.samples is samples
    assert loaded.samples.shape == (3000, 2)
    assert loaded.candidates == (candidate, candidate)
    assert loaded.sample_rate == 1000


def make_state(loaded_track, *, auto_play=True):
    from chopper.gui.sample_state import SampleState

    state = SampleState(auto_play=auto_play)
    state.load_track(loaded_track)
    return state


def record(state):
    events = {"play": [], "stop": [], "error": []}
    state.play_requested.connect(lambda item_id, token: events["play"].append((item_id, token)))
    state.stop_requested.connect(lambda: events["stop"].append(True))
    state.error_reported.connect(events["error"].append)
    return events


def begin_playback(state, events, item_id):
    state.click(item_id)
    token = events["play"][-1][1]
    state.playback_started(token)
    return token


def test_ctrl_click_marks_without_selecting_or_playing(qapp, loaded_track):
    state = make_state(loaded_track, auto_play=False)
    events = record(state)
    first, second = state.items
    state.click(first.id)
    state.click(second.id, control=True)
    assert state.active_id == first.id
    assert state.marked_ids == frozenset({second.id})
    assert state.playing_id is None
    assert events["play"] == events["stop"] == []
    state.click(second.id, control=True)
    assert state.marked_ids == frozenset()


def test_auto_click_requests_play_once_then_second_click_stops(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    first = state.items[0]
    token = begin_playback(state, events, first.id)
    assert state.active_id == state.playing_id == first.id
    assert events["play"] == [(first.id, token)]
    state.click(first.id)
    assert state.active_id == first.id
    assert state.playing_id is None
    assert events["stop"] == [True]
    assert len(events["play"]) == 1


def test_second_click_cancels_a_pending_playback(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    item_id = state.items[0].id
    state.click(item_id)
    token = events["play"][-1][1]
    state.click(item_id)
    state.playback_started(token)
    assert state.playing_id is None
    assert len(events["play"]) == len(events["stop"]) == 1


def test_ctrl_click_during_playback_preserves_playing_and_active(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    first, second = state.items
    begin_playback(state, events, first.id)
    state.click(second.id, control=True)
    assert state.active_id == state.playing_id == first.id
    assert state.marked_ids == frozenset({second.id})
    assert events["stop"] == []


def test_disabling_auto_does_not_stop_current_playback(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    first = state.items[0]
    begin_playback(state, events, first.id)
    state.set_auto_play(False)
    state.click(first.id)
    assert state.auto_play is False
    assert state.active_id == state.playing_id == first.id
    assert events["stop"] == []
    assert len(events["play"]) == 1


def test_auto_disabled_new_selection_stops_old_audio_without_starting(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    first, second = state.items
    begin_playback(state, events, first.id)
    state.set_auto_play(False)
    state.click(second.id)
    assert state.active_id == second.id
    assert state.playing_id is None
    assert events["stop"] == [True]
    assert len(events["play"]) == 1


def test_navigation_never_autoplays_but_toggle_plays_and_stops(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    first, second = state.items
    begin_playback(state, events, first.id)
    state.navigate(second.id)
    assert state.active_id == second.id
    assert state.playing_id is None
    assert len(events["play"]) == 1
    state.toggle_playback()
    token = events["play"][-1][1]
    state.playback_started(token)
    assert state.playing_id == second.id
    state.toggle_playback()
    assert state.playing_id is None
    assert events["stop"] == [True, True]


def test_natural_finish_keeps_active_and_marks(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    item_id = state.items[0].id
    state.toggle_mark(item_id)
    token = begin_playback(state, events, item_id)
    state.playback_finished(token)
    assert state.playing_id is None
    assert state.active_id == item_id
    assert state.marked_ids == frozenset({item_id})
    assert events["stop"] == []
    state.click(item_id)
    assert events["play"][-1][1] > token


@pytest.mark.parametrize("callback", ["playback_started", "playback_finished", "playback_failed"])
def test_old_completion_cannot_stop_new_playback(qapp, loaded_track, callback):
    state = make_state(loaded_track)
    events = record(state)
    first, second = state.items
    old_token = begin_playback(state, events, first.id)
    new_token = begin_playback(state, events, second.id)
    args = (old_token, "old failure") if callback == "playback_failed" else (old_token,)
    getattr(state, callback)(*args)
    assert state.active_id == state.playing_id == second.id
    assert new_token > old_token
    assert events["error"] == []


def test_old_finish_of_same_sample_cannot_stop_its_restart(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    item_id = state.items[0].id
    old_token = begin_playback(state, events, item_id)
    state.stop()
    new_token = begin_playback(state, events, item_id)
    state.playback_finished(old_token)
    assert state.playing_id == item_id
    assert new_token > old_token


def test_current_playback_error_is_visible_without_losing_marks(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    item_id = state.items[0].id
    token = begin_playback(state, events, item_id)
    state.toggle_mark(item_id)
    state.playback_failed(token, "aucune sortie audio")
    assert state.playing_id is None
    assert state.active_id == item_id
    assert state.marked_ids == frozenset({item_id})
    assert events["error"] == ["aucune sortie audio"]
    state.toggle_playback()
    assert events["play"][-1][1] > token


def test_error_while_handling_stop_is_visible_but_late_error_is_ignored(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    token = begin_playback(state, events, state.items[0].id)
    state.stop_requested.connect(lambda: state.playback_failed(token, "arrêt impossible"))
    state.stop()
    assert events["error"] == ["arrêt impossible"]
    assert state.playing_id is None
    state.playback_failed(token, "obsolete error")
    assert events["error"] == ["arrêt impossible"]


def test_reloading_track_resets_marks_and_never_reuses_ids_or_tokens(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    old_ids = {item.id for item in state.items}
    old_token = begin_playback(state, events, state.items[0].id)
    state.mark_all()
    state.load_track(loaded_track)
    assert state.active_id is state.playing_id is None
    assert state.marked_ids == frozenset()
    assert not old_ids.intersection(item.id for item in state.items)
    state.playback_started(old_token)
    for old_id in old_ids:
        state.click(old_id)
        state.toggle_mark(old_id)
    assert state.active_id is state.playing_id is None
    assert state.marked_ids == frozenset()
    new_token = begin_playback(state, events, state.items[0].id)
    assert new_token > old_token


def test_equal_candidates_have_different_ids(qapp, loaded_track):
    candidate = loaded_track.candidates[0]
    state = make_state(replace(loaded_track, candidates=(candidate, candidate)), auto_play=False)
    first, second = state.items
    assert first.id != second.id
    assert first.candidate == second.candidate
    state.click(second.id)
    state.toggle_mark(first.id)
    assert state.active_id == second.id
    assert state.marked_ids == frozenset({first.id})


def test_mark_all_and_clear_marks_do_not_change_selection_or_playback(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record(state)
    item_id = state.items[1].id
    begin_playback(state, events, item_id)
    state.mark_all()
    assert state.marked_ids == frozenset(item.id for item in state.items)
    state.clear_marks()
    state.clear_marks()
    assert state.marked_ids == frozenset()
    assert state.active_id == state.playing_id == item_id
    assert len(events["play"]) == 1
    assert events["stop"] == []


def test_clear_is_repeatable_and_ignores_late_callbacks(qapp, loaded_track):
    state = make_state(loaded_track, auto_play=False)
    events = record(state)
    state.navigate(state.items[0].id)
    state.toggle_playback()
    token = events["play"][-1][1]
    state.clear()
    state.clear()
    state.playback_started(token)
    state.playback_failed(token, "late")
    assert state.items == ()
    assert state.loaded_track is None
    assert state.active_id is state.playing_id is None
    assert state.marked_ids == frozenset()
    assert state.auto_play is False
    assert events["stop"] == [True]
    assert events["error"] == []


def test_no_active_item_or_stale_id_never_requests_audio(qapp, loaded_track):
    state = make_state(replace(loaded_track, candidates=()))
    events = record(state)
    state.toggle_playback()
    state.stop()
    state.click(-1)
    state.navigate(-1)
    state.toggle_mark(-1)
    state.mark_all()
    state.clear_marks()
    assert state.active_id is state.playing_id is None
    assert state.marked_ids == frozenset()
    assert events == {"play": [], "stop": [], "error": []}


def record_ranges(state):
    events = record(state)
    events["range"] = []
    state.range_play_requested.connect(lambda window, token: events["range"].append((window, token)))
    return events


@pytest.mark.parametrize("auto_play,auto_preview", [(True, True), (False, True), (True, False)])
def test_manual_range_obeys_auto_but_always_allows_explicit_play(qapp, loaded_track, auto_play, auto_preview):
    state = make_state(loaded_track, auto_play=auto_play)
    events = record_ranges(state)
    state.select_range((0.2, 0.8), auto_preview=auto_preview)
    assert state.can_preview and state.active_id is None
    assert state.playing_id is state.playing_window is None
    if auto_play and auto_preview:
        assert len(events["range"]) == 1 and state.has_playback
    else:
        assert events["range"] == [] and not state.has_playback
        state.toggle_playback()
    assert events["range"][0][0] == (0.2, 0.8)
    token = events["range"][0][1]
    state.playback_started(token)
    assert state.playing_window == (0.2, 0.8) and state.playing_id is None
    state.toggle_playback()
    assert not state.has_playback and state.playing_window is None
    assert events["stop"] == [True] and events["play"] == []


@pytest.mark.parametrize("callback", ["playback_started", "playback_finished", "playback_failed"])
@pytest.mark.parametrize("started", [False, True])
def test_sample_range_sample_share_tokens_and_ignore_stale_callbacks(qapp, loaded_track, callback, started):
    state = make_state(loaded_track)
    events = record_ranges(state)
    item_id = state.items[0].id
    state.click(item_id)
    first_token = events["play"][-1][1]
    if started:
        state.playback_started(first_token)
    state.select_range((0.2, 0.8))
    range_token = events["range"][-1][1]
    if started:
        state.playback_started(range_token)
    args = (first_token, "old sample error") if callback == "playback_failed" else (first_token,)
    getattr(state, callback)(*args)
    assert state.has_playback and state.playing_id is None
    assert state.playing_window == ((0.2, 0.8) if started else None)
    # The old active ID must select the sample again, not merely stop the range.
    state.click(item_id)
    sample_token = events["play"][-1][1]
    assert first_token < range_token < sample_token
    if started:
        state.playback_started(sample_token)
    args = (range_token, "old range error") if callback == "playback_failed" else (range_token,)
    getattr(state, callback)(*args)
    assert state.has_playback and state.playing_window is None
    assert state.playing_id == (item_id if started else None)
    assert len(events["play"]) == 2 and len(events["range"]) == 1
    assert events["stop"] == [True, True] and events["error"] == []


def test_ctrl_click_preserves_range_as_space_target(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record_ranges(state)
    state.select_range((0.2, 0.8))
    token = events["range"][-1][1]
    state.playback_started(token)
    state.click(state.items[1].id, control=True)
    assert state.playing_window == (0.2, 0.8) and state.active_id is None
    assert state.marked_ids == {state.items[1].id}
    assert not events["stop"] and not events["play"]
    state.toggle_playback()
    state.toggle_playback()
    assert len(events["range"]) == 2 and events["range"][-1][1] > token


def test_navigation_to_same_active_id_returns_from_range_without_autoplay(qapp, loaded_track):
    state = make_state(loaded_track, auto_play=False)
    events = record_ranges(state)
    item_id = state.items[0].id
    state.navigate(item_id)
    state.select_range((0.2, 0.8))
    state.toggle_playback()
    state.navigate(item_id)
    assert not state.has_playback and state.playing_window is None
    assert events["stop"] == [True] and not events["play"]
    state.toggle_playback()
    assert events["play"][-1][0] == item_id and len(events["range"]) == 1


@pytest.mark.parametrize("reset", ["clear", "clear_range", "load_track"])
def test_reset_removes_range_target_and_ignores_its_callbacks(qapp, loaded_track, reset):
    state = make_state(loaded_track)
    events = record_ranges(state)
    state.select_range((0.2, 0.8))
    token = events["range"][-1][1]
    if reset == "load_track":
        state.load_track(loaded_track)
    else:
        getattr(state, reset)()
        getattr(state, reset)()
    state.playback_started(token)
    state.playback_finished(token)
    state.playback_failed(token, "stale")
    state.toggle_playback()
    assert not state.can_preview and not state.has_playback
    assert state.playing_id is state.playing_window is None
    assert events["stop"] == [True] and events["error"] == []
    assert len(events["range"]) == 1 and not events["play"]
    if reset != "clear":
        state.click(state.items[0].id)
        assert events["play"][-1][1] > token


def test_current_range_finish_or_error_retains_target_for_retry(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record_ranges(state)
    state.select_range((0.2, 0.8))
    first = events["range"][-1][1]
    state.playback_started(first)
    state.playback_finished(first)
    assert state.can_preview and not state.has_playback and state.playing_window is None
    state.toggle_playback()
    second = events["range"][-1][1]
    state.playback_failed(second, "No output device")
    assert events["error"] == ["No output device"]
    assert state.can_preview and not state.has_playback and state.playing_window is None
    state.toggle_playback()
    assert first < second < events["range"][-1][1]


@pytest.mark.parametrize("kind", ["sample", "range"])
@pytest.mark.parametrize("started", [False, True])
def test_replacement_keeps_audio_analysis_and_invalidates_old_sample_generation(
    qapp, loaded_track, kind, started
):
    state = make_state(loaded_track)
    events = record_ranges(state)
    old_ids = {item.id for item in state.items}
    if kind == "sample":
        state.click(state.items[0].id)
        token = events["play"][-1][1]
    else:
        state.select_range((0.2, 0.8))
        token = events["range"][-1][1]
    if started:
        state.playback_started(token)
    state.mark_all()
    candidates = (replace(loaded_track.candidates[0], start_seconds=0.3, end_seconds=0.9),)
    state.replace_candidates(candidates)
    loaded = state.loaded_track
    assert loaded is not loaded_track
    assert loaded.samples is loaded_track.samples and loaded.analysis is loaded_track.analysis
    assert loaded.sample_rate == loaded_track.sample_rate and loaded.candidates == candidates
    assert loaded_track.candidates != candidates
    assert state.active_id is state.playing_id is None and state.playing_window is None
    assert not state.marked_ids and not state.has_playback
    assert min(item.id for item in state.items) > max(old_ids)
    for old_id in old_ids:
        state.click(old_id)
        state.toggle_mark(old_id)
    state.playback_started(token)
    state.playback_finished(token)
    state.playback_failed(token, "obsolete")
    assert not state.has_playback and not state.marked_ids and events["error"] == []
    assert events["stop"] == [True]
    assert len(events["play"]) + len(events["range"]) == 1
    if kind == "range":
        assert state.can_preview
        state.toggle_playback()
        assert events["range"][-1][0] == (0.2, 0.8) and events["range"][-1][1] > token
    else:
        assert not state.can_preview
        state.click(state.items[0].id)
        assert events["play"][-1][1] > token


def test_empty_candidate_replacement_keeps_range_without_creating_fake_sample(qapp, loaded_track):
    state = make_state(loaded_track, auto_play=False)
    events = record_ranges(state)
    state.select_range((0.2, 0.8))
    state.replace_candidates(())
    assert state.items == () and state.loaded_track.candidates == ()
    assert state.can_preview and not state.has_playback
    assert not events["range"] and not events["stop"]
    state.toggle_playback()
    assert events["range"][-1][0] == (0.2, 0.8) and not events["play"]


def test_clear_range_does_not_interrupt_a_sample_target(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record_ranges(state)
    token = begin_playback(state, events, state.items[0].id)
    state.clear_range()
    assert state.playing_id == state.items[0].id and state.has_playback
    assert not events["stop"]
    state.playback_finished(token)


def test_range_change_stops_old_preview_even_when_auto_is_disabled(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record_ranges(state)
    first = begin_playback(state, events, state.items[0].id)
    state.set_auto_play(False)
    state.select_range((0.2, 0.8))
    assert events["stop"] == [True] and not events["range"]
    assert state.can_preview and not state.has_playback
    state.toggle_playback()
    assert events["range"][-1][1] > first
    state.clear_range()
    state.toggle_playback()
    assert events["play"][-1][0] == state.items[0].id


def test_repeated_range_selection_restarts_instead_of_toggling_off(qapp, loaded_track):
    state = make_state(loaded_track)
    events = record_ranges(state)
    state.select_range((0.2, 0.8))
    first = events["range"][-1][1]
    state.select_range((0.2, 0.8))
    assert state.has_playback and len(events["range"]) == 2
    assert events["range"][-1][1] > first and events["stop"] == [True]


@pytest.mark.parametrize(
    "window",
    [
        (0.0, 0.0),
        (0.8, 0.2),
        (-1.0, 0.5),
        (0.0, 4.0),
        (float("nan"), 1.0),
        (0.0, float("inf")),
        (True, 2.0),
        (0.0,),
        "01",
        ("0", 1.0),
    ],
)
def test_invalid_range_does_not_stop_or_replace_valid_target(qapp, loaded_track, window):
    state = make_state(loaded_track)
    events = record_ranges(state)
    state.select_range((0.2, 0.8))
    token = events["range"][-1][1]
    state.playback_started(token)
    with pytest.raises(ValueError, match="range"):
        state.select_range(window)
    assert state.has_playback and state.playing_window == (0.2, 0.8)
    assert len(events["range"]) == 1 and not events["stop"]


def test_range_and_replacement_without_loaded_audio_are_noops(qapp, loaded_track):
    state = make_state(loaded_track)
    state.clear()
    events = record_ranges(state)
    state.select_range((0.2, 0.8))
    state.replace_candidates(loaded_track.candidates)
    state.toggle_playback()
    assert state.loaded_track is None and state.items == ()
    assert not state.can_preview and not state.has_playback
    assert events == {"play": [], "stop": [], "error": [], "range": []}


def test_boundary_edits_keep_other_boundary_and_reset_on_recut(qapp, loaded_track):
    from chopper.gui.sample_state import SampleState

    state = SampleState(auto_play=False)
    state.load_track(loaded_track)
    sample = state.items[0]
    original = sample.candidate
    state.click(sample.id)
    state.toggle_mark(sample.id)
    assert state.set_boundary_offset(sample.id, "start", 20)
    assert state.set_boundary_offset(sample.id, "end", -30)
    assert state.set_boundary_offset(sample.id, "start", 0)
    edited = state.items[0]
    assert edited.candidate.start_seconds == original.start_seconds
    assert edited.end_offset_ms == -30
    assert state.loaded_track is loaded_track
    assert state.active_id == sample.id and sample.id in state.marked_ids
    state.replace_candidates(loaded_track.candidates)
    assert state.items[0].end_offset_ms == 0
    assert not state.set_boundary_offset(sample.id, "end", -30)


def test_boundary_edit_stops_only_its_own_preview(qapp, loaded_track):
    from chopper.gui.sample_state import SampleState

    state = SampleState(auto_play=False)
    state.load_track(loaded_track)
    first, second = state.items
    requests, stops = [], []
    state.play_requested.connect(lambda item_id, token: requests.append((item_id, token)))
    state.stop_requested.connect(lambda: stops.append(True))
    state.click(first.id)
    state.toggle_playback()
    state.playback_started(requests[0][1])
    assert state.set_boundary_offset(second.id, "end", -20)
    assert state.playing_id == first.id and not stops
    assert state.set_boundary_offset(first.id, "end", -20)
    assert state.playing_id is None and stops == [True]
    assert len(requests) == 1
