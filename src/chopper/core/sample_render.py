"""Render the same source excerpt for preview and export."""

import math

import librosa
import numpy as np

from chopper.core.models import Candidate

# Limit changed-speed output to 64 MiB of float32 audio (all channels combined).
MAX_RENDER_VALUES = 16 * 1024 * 1024


def _source_frames(frame_count: int, sample_rate: int, candidate: Candidate) -> tuple[int, int]:
    if (
        not math.isfinite(sample_rate)
        or sample_rate <= 0
        or not math.isfinite(candidate.start_seconds)
        or not math.isfinite(candidate.end_seconds)
        or candidate.end_seconds <= candidate.start_seconds
    ):
        raise ValueError("Invalid audio or sample boundaries.")
    duration = frame_count / sample_rate
    start = round(min(duration, max(0.0, candidate.start_seconds)) * sample_rate)
    end = round(min(duration, max(0.0, candidate.end_seconds)) * sample_rate)
    if end <= start:
        raise ValueError("This sample is empty (zero length).")
    return start, end


def _output_frames(source_frames: int, rate: float, channels: int) -> int:
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("Playback speed must be positive and finite.")
    if rate == 1:
        return source_frames
    size = source_frames / rate
    if not math.isfinite(size) or size >= MAX_RENDER_VALUES // channels + 0.5:
        raise ValueError("Changed-speed audio exceeds the render size limit.")
    frames = math.floor(size + 0.5)
    if frames < 1:
        raise ValueError("Changed-speed audio is empty (zero length).")
    return frames


def rendered_frame_count(
    frame_count: int, sample_rate: int, candidate: Candidate, *, channels: int = 1
) -> int:
    if channels < 1:
        raise ValueError("Invalid audio channel count.")
    start, end = _source_frames(frame_count, sample_rate, candidate)
    return _output_frames(end - start, candidate.playback_rate, channels)


def render_candidate(samples: np.ndarray, sample_rate: int, candidate: Candidate) -> np.ndarray:
    if samples.ndim not in (1, 2) or (samples.ndim == 2 and not samples.shape[1]):
        raise ValueError("Invalid audio shape.")
    start, end = _source_frames(len(samples), sample_rate, candidate)
    channels = samples.shape[1] if samples.ndim == 2 else 1
    rate = candidate.playback_rate
    frames = _output_frames(end - start, rate, channels)
    segment = samples[start:end]
    if not np.isfinite(segment).all():
        raise ValueError("This sample contains non-finite audio values.")
    if rate == 1:
        return segment
    # Resample at the inverse speed ratio, but play and write at the original rate.
    rendered = librosa.resample(
        segment.astype(np.float32, copy=False),
        orig_sr=rate,
        target_sr=1.0,
        res_type="soxr_hq",
        fix=False,
        axis=0,
    )
    if len(rendered) != frames or not np.isfinite(rendered).all():
        raise ValueError("Unexpected changed-speed audio output.")
    # Match the PCM range before either preview or export clips filter overshoot.
    np.clip(rendered, -1.0, 1.0, out=rendered)
    return rendered
