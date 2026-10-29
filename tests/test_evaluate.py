import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def evaluator():
    path = Path(__file__).parents[1] / "evaluate.py"
    spec = importlib.util.spec_from_file_location("audio_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_event_matching_measures_delay_and_never_reuses_truth(evaluator):
    result = evaluator.match_events([1.0, 2.0], [1.02, 1.03, 2.02], 0.1)
    assert result["matched"] == 2
    assert result["false_positives"] == 1
    assert result["missed"] == 0
    assert result["mae_ms"] == pytest.approx(20)
    assert result["f1"] == pytest.approx(0.8)


def test_matching_maximizes_matches_before_minimizing_delay(evaluator):
    result = evaluator.match_events([0.0, 0.1], [0.09, 0.19], 0.1)
    assert result["matched"] == 2
    assert result["mae_ms"] == pytest.approx(90)


def test_missing_detection_is_not_a_perfect_zero_error(evaluator):
    result = evaluator.match_events([1.0], [], 0.1)
    assert result["f1"] == 0
    assert result["missed"] == 1
    assert result["mae_ms"] is None
    assert evaluator.match_events([], [], 0.1)["f1"] == 1
    assert evaluator.match_events([], [1.0], 0.1)["f1"] == 0


def test_score_uses_raw_tempo_error_and_non_applicable_metrics(evaluator):
    truth = {
        "kind": "rhythm",
        "tempo_bpm": 120,
        "sample_rate": 1000,
        "loop_start_samples": [1000],
        "onset_samples": [],
    }
    score = evaluator.score_case(truth, {"tempo_bpm": 60, "loop_starts": [1.02], "onset_times": []})
    assert score["tempo_error_bpm"] == 60
    assert score["tempo_score"] == 0.5
    assert score["loops"]["mae_ms"] == pytest.approx(20)
    assert score["shots"] is None
    truth.update(kind="silence", tempo_bpm=None, loop_start_samples=[])
    score = evaluator.score_case(truth, {"tempo_bpm": 120, "loop_starts": [1], "onset_times": [1]})
    assert score["tempo_error_bpm"] is None
    assert score["loops"]["f1"] == score["shots"]["f1"] == 0


def test_aggregation_does_not_weight_cases_by_number_of_attacks(evaluator):
    cases = [
        {
            "tempo_error_bpm": 0,
            "tempo_score": 1,
            "loops": {"f1": 1, "mae_ms": 0},
            "shots": {"f1": 1, "mae_ms": 0},
        },
        {
            "tempo_error_bpm": None,
            "tempo_score": None,
            "loops": {"f1": 0, "mae_ms": None},
            "shots": {"f1": 0, "mae_ms": None},
        },
    ]
    result = evaluator.summarize(cases)
    assert result["score"] == pytest.approx(100 * 2 / 3)
    assert result["loop_f1"] == result["shot_f1"] == 0.5
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("reference,detected", [([float("nan")], []), ([], [-1]), ([], [float("inf")])])
def test_metrics_reject_invalid_times(evaluator, reference, detected):
    with pytest.raises(ValueError):
        evaluator.match_events(reference, detected, 0.1)


def test_corpus_filters_split_checks_hash_and_rejects_escape(evaluator, tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    sf.write(audio, np.zeros(22050), 22050)
    case = {
        "id": "test",
        "file": "clip.wav",
        "split": "tune",
        "kind": "silence",
        "tempo_bpm": None,
        "sample_rate": 22050,
        "loop_start_samples": [],
        "onset_samples": [],
        "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
    }
    manifest = tmp_path / "truth.json"
    manifest.write_text(json.dumps({"schema_version": 1, "cases": [case]}))
    assert evaluator.evaluate_corpus(tmp_path, "validation", "cpu")["cases"] == []

    def unavailable(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(evaluator, "detect", unavailable)
    with pytest.raises(RuntimeError, match="model unavailable"):
        evaluator.evaluate_corpus(tmp_path, "tune", "cpu")
    case["file"] = "../clip.wav"
    manifest.write_text(json.dumps({"schema_version": 1, "cases": [case]}))
    with pytest.raises(ValueError, match="corpus"):
        evaluator.evaluate_corpus(tmp_path, "tune", "cpu")


def test_partial_read_keeps_source_unchanged_and_converts_positions(evaluator, tmp_path, monkeypatch):
    source = tmp_path / "source.flac"
    sf.write(source, np.column_stack([np.linspace(-0.5, 0.5, 10000)] * 2), 1000)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    received = []

    def inference(path, device):
        samples, rate = sf.read(path, always_2d=True)
        received.append((len(samples), rate, samples.shape[1]))
        return {"tempo_bpm": 120, "loop_starts": [0.2], "onset_times": [0.4]}

    monkeypatch.setattr(evaluator, "detect", inference)
    result = evaluator.evaluate_real_passages(tmp_path, "cpu")
    assert received == [(10000, 1000, 2)] * 2
    assert result["cases"][0]["start_seconds"] == 0
    assert result["cases"][0]["loop_starts_source"] == [0.2]
    assert result["cases"][0]["ground_truth"] is None
    assert "score" not in result
    assert before == hashlib.sha256(source.read_bytes()).hexdigest()


def test_real_passages_use_fixed_offsets_and_read_only_requested_frames(evaluator, tmp_path, monkeypatch):
    source = tmp_path / "source.flac"
    sf.write(source, np.zeros(120000), 1000)
    monkeypatch.setattr(
        evaluator, "detect", lambda *args: {"tempo_bpm": 120, "loop_starts": [0.2], "onset_times": [0.4]}
    )
    result = evaluator.evaluate_real_passages(tmp_path, "cpu")
    assert [case["start_seconds"] for case in result["cases"]] == [30, 72]
    assert [case["end_seconds"] for case in result["cases"]] == [60, 102]
    assert result["cases"][1]["loop_starts_source"] == [72.2]
