import time

import numpy as np
import pytest
import sounddevice as sd
from PySide6.QtCore import QTimer

from choppeur.core.models import Candidate, CandidateType


class HostStream:
    def __init__(self):
        self.running = True
        self.poll_error = None

    @property
    def active(self):
        if self.poll_error is not None:
            raise self.poll_error
        return self.running


class AudioHost:
    """Only the PortAudio boundary is replaced; Qt timers and the player are real."""

    def __init__(self):
        self.streams = []
        self.received = []
        self.play_error = None
        self.stream_error = None
        self.stop_error = None
        self.players = []

    def play(self, data, samplerate, *, loop, blocking):
        if self.play_error is not None:
            raise self.play_error
        self.received.append((data.copy(), samplerate, loop, blocking))
        self.streams.append(HostStream())

    def get_stream(self):
        if self.stream_error is not None:
            raise self.stream_error
        return self.streams[-1]

    def stop(self, *, ignore_errors):
        assert ignore_errors is False
        if self.stop_error is not None:
            raise self.stop_error
        for stream in self.streams:
            stream.running = False


@pytest.fixture
def audio_host(monkeypatch, qapp):
    host = AudioHost()
    monkeypatch.setattr(sd, "play", host.play)
    monkeypatch.setattr(sd, "get_stream", host.get_stream)
    monkeypatch.setattr(sd, "stop", host.stop)
    yield host
    host.stop_error = None
    for player in host.players:
        player.stop()
        player.deleteLater()
    qapp.processEvents()


def make_player(host):
    from choppeur.gui.preview_player import PreviewPlayer

    player = PreviewPlayer()
    host.players.append(player)
    events = {"started": [], "finished": [], "failed": []}
    player.started.connect(events["started"].append)
    player.finished.connect(events["finished"].append)
    player.failed.connect(lambda token, message: events["failed"].append((token, message)))
    return player, events


def wait_until(qapp, condition):
    deadline = time.monotonic() + 1.0
    while not condition():
        qapp.processEvents()
        assert time.monotonic() < deadline, "condition non atteinte à temps"


def test_player_sends_the_exact_stereo_segment_once_without_mutating_source(audio_host, loaded_track):
    player, events = make_player(audio_host)
    before = loaded_track.samples.copy()
    player.play(loaded_track.samples, loaded_track.sample_rate, loaded_track.candidates[1], 7)
    assert events == {"started": [7], "finished": [], "failed": []}
    assert len(audio_host.received) == 1
    segment, rate, loop, blocking = audio_host.received[0]
    np.testing.assert_array_equal(segment, before[1000:1200])
    np.testing.assert_array_equal(loaded_track.samples, before)
    assert segment.shape == (200, 2)
    assert rate == 1000
    assert loop is blocking is False


def test_player_preserves_mono_and_clips_bounds_like_the_exporter(audio_host, loaded_track):
    player, events = make_player(audio_host)
    mono = loaded_track.samples[:, 0].copy()
    candidate = Candidate(CandidateType.ONE_SHOT, -0.1, 4.0, 1.0)
    player.play(mono, 1000, candidate, 3)
    np.testing.assert_array_equal(audio_host.received[0][0], mono)
    assert audio_host.received[0][0].ndim == 1
    assert events["started"] == [3]


def test_natural_finish_tracks_stream_activity_not_theoretical_duration(qapp, audio_host, loaded_track):
    player, events = make_player(audio_host)
    short = Candidate(CandidateType.ONE_SHOT, 0.0, 0.001, 1.0)
    player.play(loaded_track.samples, 1000, short, 9)
    observed = []

    def after_tick():
        observed.append(len(events["finished"]))
        if len(observed) == 3:
            audio_host.streams[-1].running = False

    player.findChild(QTimer).timeout.connect(after_tick)
    wait_until(qapp, lambda: bool(events["finished"]))
    assert observed[:3] == [0, 0, 0]
    assert events["finished"] == [9]
    assert events["failed"] == []


def test_new_playback_never_polls_the_replaced_stream(qapp, audio_host, loaded_track):
    player, events = make_player(audio_host)
    player.play(loaded_track.samples, 1000, loaded_track.candidates[0], 1)
    old_stream = audio_host.streams[-1]
    player.play(loaded_track.samples, 1000, loaded_track.candidates[1], 2)
    old_stream.poll_error = RuntimeError("obsolete stream")
    ticks = []
    player.findChild(QTimer).timeout.connect(lambda: ticks.append(True))
    wait_until(qapp, lambda: len(ticks) >= 2)
    assert events["finished"] == [1]
    assert events["started"] == [1, 2]
    assert events["failed"] == []
    assert sum(stream.running for stream in audio_host.streams) == 1
    audio_host.streams[-1].running = False
    wait_until(qapp, lambda: events["finished"] == [1, 2])


def test_stop_is_repeatable_and_emits_only_one_completion(audio_host, loaded_track):
    player, events = make_player(audio_host)
    player.play(loaded_track.samples, 1000, loaded_track.candidates[0], 11)
    player.stop()
    player.stop()
    assert events["finished"] == [11]
    assert not any(stream.running for stream in audio_host.streams)
    assert events["failed"] == []


def test_play_error_does_not_report_started_and_can_be_retried(audio_host, loaded_track):
    player, events = make_player(audio_host)
    audio_host.play_error = RuntimeError("aucun périphérique")
    player.play(loaded_track.samples, 1000, loaded_track.candidates[0], 1)
    assert events["started"] == events["finished"] == []
    assert events["failed"][0][0] == 1
    assert "aucun périphérique" in events["failed"][0][1]
    audio_host.play_error = None
    player.play(loaded_track.samples, 1000, loaded_track.candidates[0], 2)
    assert events["started"] == [2]


def test_get_stream_error_stops_output_that_already_started(audio_host, loaded_track):
    player, events = make_player(audio_host)
    audio_host.stream_error = RuntimeError("flux indisponible")
    player.play(loaded_track.samples, 1000, loaded_track.candidates[0], 2)
    assert events["started"] == events["finished"] == []
    assert events["failed"][0][0] == 2
    assert not any(stream.running for stream in audio_host.streams)


def test_stream_poll_error_is_reported_once_and_stops_output(qapp, audio_host, loaded_track):
    player, events = make_player(audio_host)
    player.play(loaded_track.samples, 1000, loaded_track.candidates[0], 5)
    audio_host.streams[-1].poll_error = RuntimeError("périphérique déconnecté")
    wait_until(qapp, lambda: bool(events["failed"]))
    assert len(events["failed"]) == 1
    assert events["failed"][0][0] == 5
    assert "déconnecté" in events["failed"][0][1]
    assert events["finished"] == []
    assert not audio_host.streams[-1].running


def test_failed_stop_is_visible_and_prevents_overlapping_new_audio(audio_host, loaded_track):
    player, events = make_player(audio_host)
    player.play(loaded_track.samples, 1000, loaded_track.candidates[0], 1)
    audio_host.stop_error = RuntimeError("arrêt impossible")
    player.play(loaded_track.samples, 1000, loaded_track.candidates[1], 2)
    assert len(audio_host.streams) == 1
    assert events["started"] == [1]
    assert {token for token, _ in events["failed"]} == {1, 2}
    audio_host.stop_error = None
    player.play(loaded_track.samples, 1000, loaded_track.candidates[1], 3)
    assert events["started"] == [1, 3]
    assert sum(stream.running for stream in audio_host.streams) == 1


@pytest.mark.parametrize(
    ("rate", "start", "end", "shape"),
    [
        (0, 0, 1, (10,)),
        (1000, 0, 0, (10,)),
        (1000, 5, 6, (10,)),
        (1000, float("nan"), 1, (10,)),
        (1000, 0, float("inf"), (10,)),
        (1000, 0, 1, (0,)),
        (1000, 0, 1, (10, 0)),
        (1000, 0, 1, (10, 2, 2)),
        (1000, -2, -1, (3000,)),
        (1000, 1e308, 1.1e308, (10,)),
    ],
)
def test_invalid_audio_or_bounds_never_reaches_portaudio(audio_host, rate, start, end, shape):
    player, events = make_player(audio_host)
    player.play(np.zeros(shape, dtype=np.float32), rate, Candidate(CandidateType.ONE_SHOT, start, end, 1), 4)
    assert audio_host.received == []
    assert events["started"] == []
    assert len(events["failed"]) == 1
    assert events["failed"][0][0] == 4


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf")])
def test_nonfinite_audio_in_the_segment_is_rejected(audio_host, loaded_track, invalid_value):
    player, events = make_player(audio_host)
    samples = loaded_track.samples.copy()
    samples[1000, 1] = invalid_value
    player.play(samples, 1000, loaded_track.candidates[1], 8)
    assert audio_host.received == []
    assert events["started"] == []
    assert events["failed"][0][0] == 8


def test_nonfinite_audio_outside_the_segment_does_not_reject_valid_excerpt(audio_host, loaded_track):
    player, events = make_player(audio_host)
    samples = loaded_track.samples.copy()
    samples[2000, 1] = float("nan")
    player.play(samples, 1000, loaded_track.candidates[1], 8)
    assert events["started"] == [8]
    assert np.isfinite(audio_host.received[0][0]).all()


def test_state_and_player_keep_stereo_marks_and_ignore_old_finish(qapp, audio_host, loaded_track):
    from choppeur.gui.sample_state import SampleState

    state = SampleState()
    state.load_track(loaded_track)
    player, events = make_player(audio_host)

    def play_item(item_id, token):
        candidate = next(item.candidate for item in state.items if item.id == item_id)
        player.play(loaded_track.samples, loaded_track.sample_rate, candidate, token)

    state.play_requested.connect(play_item)
    state.stop_requested.connect(player.stop)
    player.started.connect(state.playback_started)
    player.finished.connect(state.playback_finished)
    player.failed.connect(state.playback_failed)
    first, second = state.items
    state.click(first.id)
    old_token = events["started"][-1]
    state.click(second.id, control=True)
    state.click(second.id)
    player.finished.emit(old_token)
    assert state.active_id == state.playing_id == second.id
    assert state.marked_ids == frozenset({second.id})
    np.testing.assert_array_equal(audio_host.received[-1][0], loaded_track.samples[1000:1200])
    audio_host.streams[-1].running = False
    wait_until(qapp, lambda: state.playing_id is None)
    assert state.active_id == second.id
    assert state.marked_ids == frozenset({second.id})
