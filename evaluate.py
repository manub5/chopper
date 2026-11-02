"""Reproducible evaluation of Choppeur's real detection pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path

import soundfile as sf


def match_events(reference: list[float], detected: list[float], tolerance_seconds: float) -> dict:
    """Maximize chronological one-to-one matches, then minimize absolute error."""
    if not math.isfinite(tolerance_seconds) or tolerance_seconds < 0:
        raise ValueError("Invalid event tolerance")
    if any(not math.isfinite(t) or t < 0 for t in reference + detected):
        raise ValueError("Invalid event time")
    reference, detected = sorted(reference), sorted(detected)
    # Each state stores match count and total absolute error; pairs cannot cross.
    table = [[(0, 0.0)] * (len(detected) + 1) for _ in range(len(reference) + 1)]
    choices = {}
    for i, expected in enumerate(reference, start=1):
        for j, actual in enumerate(detected, start=1):
            options = [(table[i - 1][j], "reference"), (table[i][j - 1], "detected")]
            error = abs(expected - actual)
            if error <= tolerance_seconds + 1e-12:
                count, cost = table[i - 1][j - 1]
                options.append(((count + 1, cost + error), "match"))
            state, choice = max(options, key=lambda option: (option[0][0], -option[0][1]))
            table[i][j] = state
            choices[i, j] = choice
    i, j = len(reference), len(detected)
    errors = []
    while i and j:
        choice = choices[i, j]
        if choice == "match":
            errors.append(1000 * abs(reference[i - 1] - detected[j - 1]))
            i, j = i - 1, j - 1
        elif choice == "reference":
            i -= 1
        else:
            j -= 1
    matched = len(errors)
    total = len(reference) + len(detected)
    return {
        "matched": matched,
        "missed": len(reference) - matched,
        "false_positives": len(detected) - matched,
        "precision": matched / len(detected) if detected else float(not reference),
        "recall": matched / len(reference) if reference else float(not detected),
        "f1": 2 * matched / total if total else 1.0,
        "mae_ms": sum(errors) / matched if matched else None,
    }


def score_case(truth: dict, detection: dict) -> dict:
    rate = truth["sample_rate"]
    expected_tempo = truth["tempo_bpm"]
    actual_tempo = detection["tempo_bpm"]
    if not math.isfinite(actual_tempo) or actual_tempo < 0:
        raise ValueError("Invalid detected tempo")
    tempo_error = abs(expected_tempo - actual_tempo) if expected_tempo is not None else None
    return {
        "tempo_error_bpm": tempo_error,
        "tempo_score": max(0.0, 1 - tempo_error / expected_tempo) if tempo_error is not None else None,
        "loops": match_events([n / rate for n in truth["loop_start_samples"]], detection["loop_starts"], 0.1),
        "shots": (
            match_events([n / rate for n in truth["onset_samples"]], detection["onset_times"], 0.1)
            if truth["kind"] != "rhythm"
            else None
        ),
    }


def _mean(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def summarize(cases: list[dict]) -> dict:
    tempo = _mean([case["tempo_score"] for case in cases])
    loop_f1 = _mean([case["loops"]["f1"] for case in cases])
    shot_f1 = _mean([case["shots"]["f1"] for case in cases if case["shots"] is not None])
    overall = _mean([tempo, loop_f1, shot_f1])
    return {
        "score": 100 * overall if overall is not None else None,
        "tempo_mae_bpm": _mean([case["tempo_error_bpm"] for case in cases]),
        "tempo_score": tempo,
        "loop_f1": loop_f1,
        "shot_f1": shot_f1,
        "loop_matched_mae_ms": _mean([case["loops"]["mae_ms"] for case in cases]),
        "shot_matched_mae_ms": _mean(
            [case["shots"]["mae_ms"] for case in cases if case["shots"] is not None]
        ),
    }


def detect(path: Path, device: str) -> dict:
    from chopper.core import audio_io, candidates, onsets, rhythm

    samples, rate = audio_io.load(path)
    bpm, beats, downbeats = rhythm.analyze_rhythm(path, device=device)
    attacks = onsets.detect_onsets(samples, rate)
    loops = candidates.find_loop_candidates(
        samples, rate, bpm, downbeats, lengths_bars=(1,), max_candidates=128
    )
    shots = candidates.find_one_shot_candidates(samples, rate, attacks, max_candidates=128)
    return {
        "tempo_bpm": bpm,
        "beat_times": list(beats),
        "downbeat_times": list(downbeats),
        "loop_starts": [loop.start_seconds for loop in loops],
        "loop_ends": [loop.end_seconds for loop in loops],
        "onset_times": [shot.start_seconds for shot in shots],
    }


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def evaluate_corpus(corpus: Path, split: str, device: str) -> dict:
    corpus = corpus.resolve()
    truth = json.loads((corpus / "truth.json").read_text())
    if truth["schema_version"] != 1 or split not in ("all", "tune", "validation"):
        raise ValueError("Invalid corpus schema or split")
    results = []
    for case in truth["cases"]:
        if split != "all" and case["split"] != split:
            continue
        path = (corpus / case["file"]).resolve()
        if not path.is_relative_to(corpus) or path.suffix.lower() != ".wav":
            raise ValueError("Audio path escapes corpus or is not WAV")
        if _digest(path) != case["sha256"]:
            raise ValueError(f"Corpus audio changed: {case['id']}")
        info = sf.info(path)
        if info.samplerate != case["sample_rate"]:
            raise ValueError(f"Corpus sample rate changed: {case['id']}")
        started = time.monotonic()
        detection = detect(path, device)
        results.append(
            {
                "id": case["id"],
                "split": case["split"],
                "kind": case["kind"],
                "elapsed_seconds": time.monotonic() - started,
                "detection": detection,
                **score_case(case, detection),
            }
        )
        print(f"Analysé : {case['id']}", file=sys.stderr, flush=True)
    return {"split": split, "cases": results, "summary": summarize(results)}


def evaluate_real_passages(root: Path, device: str) -> dict:
    results = []
    paths = sorted(path for path in root.iterdir() if path.suffix.lower() == ".flac" and path.is_file())
    if not paths:
        raise ValueError("No FLAC files found")
    for path in paths:
        before = _digest(path)
        info = sf.info(path)
        for fraction in (0.25, 0.6):
            frames = min(info.frames, round(30 * info.samplerate))
            start = min(round(fraction * info.frames), info.frames - frames)
            if frames <= 0:
                raise ValueError(f"Empty FLAC: {path.name}")
            samples, rate = sf.read(path, start=start, frames=frames, dtype="float32", always_2d=True)
            started = time.monotonic()
            with tempfile.TemporaryDirectory(prefix="choppeur-eval-") as temporary:
                excerpt = Path(temporary) / "excerpt.wav"
                sf.write(excerpt, samples, rate, subtype="FLOAT")
                detection = detect(excerpt, device)
            offset = start / rate
            results.append(
                {
                    "file": path.name,
                    "sha256": before,
                    "ground_truth": None,
                    "start_frame": start,
                    "end_frame": start + len(samples),
                    "sample_rate": rate,
                    "start_seconds": offset,
                    "end_seconds": (start + len(samples)) / rate,
                    "elapsed_seconds": time.monotonic() - started,
                    "detection": detection,
                    "loop_starts_source": [offset + t for t in detection["loop_starts"]],
                    "onset_times_source": [offset + t for t in detection["onset_times"]],
                }
            )
            print(
                f"Analysé : {path.name} [{offset:.3f}, {(start + len(samples)) / rate:.3f}]",
                file=sys.stderr,
                flush=True,
            )
        if _digest(path) != before:
            raise RuntimeError(f"Source changed during evaluation: {path.name}")
    return {"ground_truth": None, "cases": results, "source_hashes_unchanged": True}


def metadata(device: str, threads: int) -> dict:
    import torch

    checkpoint = Path(torch.hub.get_dir()) / "checkpoints" / "beat_this-final0.ckpt"
    return {
        "versions": {name: version(name) for name in ("librosa", "beat-this", "torch", "soundfile", "numpy")},
        "device": device,
        "threads": threads,
        "checkpoint": "final0",
        "dbn": False,
        "checkpoint_sha256": _digest(checkpoint) if checkpoint.is_file() else None,
        "parameters": {"loop_lengths_bars": [1], "max_candidates": 128, "tolerance_ms": 100},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path(__file__).parent / "tests" / "corpus")
    parser.add_argument("--split", choices=("all", "tune", "validation"), default="all")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--real-root", type=Path)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    # Model downloads stay outside the user's home by default.
    os.environ.setdefault("TORCH_HOME", str(Path(tempfile.gettempdir()) / "choppeur-eval-torch"))
    import torch

    torch.set_num_threads(args.threads)
    try:
        result = (
            evaluate_real_passages(args.real_root, args.device)
            if args.real_root
            else evaluate_corpus(args.corpus, args.split, args.device)
        )
        result["metadata"] = metadata(args.device, args.threads)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            if args.output.suffix.lower() != ".json":
                raise ValueError("Output must be a new .json file, never an audio source")
            with args.output.open("x") as stream:
                stream.write(text)
        print(text)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Évaluation interrompue, aucun score inventé : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
