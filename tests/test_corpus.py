import hashlib
import json
import runpy
from pathlib import Path

import numpy as np
import soundfile as sf


def generate(destination):
    module = runpy.run_path(Path(__file__).parent / "corpus" / "generate.py")
    return module["generate_corpus"](destination)


def test_corpus_is_deterministic_and_annotations_stay_in_bounds(tmp_path):
    first = generate(tmp_path / "first")
    second = generate(tmp_path / "second")
    assert first.read_bytes() == second.read_bytes()
    truth = json.loads(first.read_text())
    assert len(truth["cases"]) == 10
    assert sum(case["split"] == "tune" for case in truth["cases"]) == 6
    assert sum(case["split"] == "validation" for case in truth["cases"]) == 4
    for case in truth["cases"]:
        audio = first.parent / case["file"]
        other = second.parent / case["file"]
        assert hashlib.sha256(audio.read_bytes()).digest() == hashlib.sha256(other.read_bytes()).digest()
        info = sf.info(audio)
        assert info.samplerate == case["sample_rate"] == 22050
        for key in ("beat_samples", "loop_start_samples", "onset_samples"):
            assert all(0 <= sample < info.frames for sample in case[key])


def test_shifted_rhythm_has_exact_known_start_and_tempo(tmp_path):
    truth_path = generate(tmp_path)
    case = next(case for case in json.loads(truth_path.read_text())["cases"] if case["id"] == "tune_120")
    audio, sr = sf.read(tmp_path / case["file"])
    assert case["tempo_bpm"] == 120.0
    assert case["beat_samples"][:3] == [11025, 22050, 33075]
    assert case["loop_start_samples"][:2] == [11025, 55125]
    assert np.flatnonzero(audio)[0] == 11025
    assert sr == 22050


def test_silence_and_isolated_shots_have_independent_truth(tmp_path):
    truth_path = generate(tmp_path)
    cases = json.loads(truth_path.read_text())["cases"]
    for case in cases:
        if case["kind"] == "silence":
            audio, _ = sf.read(tmp_path / case["file"])
            assert not np.any(audio)
            assert case["tempo_bpm"] is None
            assert case["loop_start_samples"] == []
        if case["kind"] == "shots":
            audio, _ = sf.read(tmp_path / case["file"])
            starts = np.flatnonzero((audio != 0) & np.r_[True, audio[:-1] == 0])
            assert starts.tolist() == case["onset_samples"]
            assert case["tempo_bpm"] is None
