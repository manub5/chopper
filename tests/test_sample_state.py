from dataclasses import replace

import numpy as np
import pytest

from choppeur.core.models import Analysis, Candidate, CandidateType, Track


def test_loaded_track_preserves_original_audio_and_equal_candidates(tmp_path):
    from choppeur.gui.presentation import LoadedTrack

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
    from choppeur.gui.sample_state import SampleState

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
