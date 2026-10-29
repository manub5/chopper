"""Generate redistributable audio with sample-accurate, detector-independent truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 22050


def _pulse(frequency: float, duration: float, decay: float) -> np.ndarray:
    times = np.arange(round(duration * SAMPLE_RATE)) / SAMPLE_RATE
    return np.cos(2 * np.pi * frequency * times) * np.exp(-decay * times)


def generate_corpus(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    cases = []
    rhythms = [
        ("tune_90", "tune", 90.0, 0.25, False),
        ("tune_120", "tune", 120.0, 0.5, False),
        ("tune_150", "tune", 150.0, 0.125, False),
        ("tune_syncopated", "tune", 120.0, 0.375, True),
        ("validation_105", "validation", 105.0, 0.4, False),
        ("validation_135", "validation", 135.0, 0.625, True),
    ]
    for case_id, split, bpm, offset, syncopated in rhythms:
        period = 60 / bpm
        beats = [round((offset + i * period) * SAMPLE_RATE) for i in range(33)]
        signal = np.zeros(round((offset + 32 * period + 0.4) * SAMPLE_RATE))
        rng = np.random.default_rng(20261029)
        for i, start in enumerate(beats):
            pulse = _pulse(55 if i % 4 == 0 else 85, 0.18, 35)
            signal[start : start + len(pulse)] += (0.65 if i % 4 == 0 else 0.3) * pulse
            if i % 2:
                snare = rng.uniform(-1, 1, round(0.09 * SAMPLE_RATE))
                snare *= np.exp(-np.arange(len(snare)) / (0.02 * SAMPLE_RATE))
                signal[start : start + len(snare)] += 0.25 * snare
            if i < 32:
                hat_start = round((offset + (i + (0.65 if syncopated else 0.5)) * period) * SAMPLE_RATE)
                hat = 0.09 * _pulse(5000, 0.025, 160)
                signal[hat_start : hat_start + len(hat)] += hat
        cases.append(_write(destination, case_id, split, "rhythm", signal, bpm, beats, beats[::4][:-1], []))

    for split, positions in (("tune", [0.25, 1.1, 2.35, 3.6]), ("validation", [0.4, 1.45, 2.8, 4.1])):
        signal = np.zeros(5 * SAMPLE_RATE)
        starts = [round(position * SAMPLE_RATE) for position in positions]
        times = np.arange(round(0.12 * SAMPLE_RATE)) / SAMPLE_RATE
        pulse = 0.4 * (0.6 + 0.4 * np.cos(2 * np.pi * 180 * times)) * np.exp(-40 * times)
        for start in starts:
            signal[start : start + len(pulse)] = pulse
        cases.append(_write(destination, f"{split}_shots", split, "shots", signal, None, [], [], starts))
        silence = np.zeros(5 * SAMPLE_RATE)
        cases.append(_write(destination, f"{split}_silence", split, "silence", silence, None, [], [], []))

    truth_path = destination / "truth.json"
    truth_path.write_text(
        json.dumps({"schema_version": 1, "seed": 20261029, "cases": cases}, indent=2, allow_nan=False) + "\n"
    )
    return truth_path


def _write(destination, case_id, split, kind, signal, bpm, beats, loops, onsets):
    path = destination / f"{case_id}.wav"
    sf.write(path, signal, SAMPLE_RATE, subtype="PCM_16")
    return {
        "id": case_id,
        "file": path.name,
        "split": split,
        "kind": kind,
        "sample_rate": SAMPLE_RATE,
        "tempo_bpm": bpm,
        "beat_samples": beats,
        "loop_start_samples": loops,
        "onset_samples": onsets,
        "beat_seconds": [sample / SAMPLE_RATE for sample in beats],
        "loop_start_seconds": [sample / SAMPLE_RATE for sample in loops],
        "onset_seconds": [sample / SAMPLE_RATE for sample in onsets],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path(__file__).parent)
    print(generate_corpus(parser.parse_args().destination))
