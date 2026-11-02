"""Export batches with partial results and durable WAV files for native drags."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from chopper.core import audio_io
from chopper.core.models import Candidate, Track


@dataclass(frozen=True)
class ExportReport:
    paths: tuple[Path, ...]
    error: str | None = None


def export_batch(
    samples: np.ndarray,
    sample_rate: int,
    track: Track,
    candidates: tuple[Candidate, ...],
    destination: Path,
    file_format: str,
) -> ExportReport:
    if file_format not in {"wav", "flac"}:
        return ExportReport((), "Unsupported export format (WAV or FLAC only).")
    paths: list[Path] = []
    for candidate in candidates:
        try:
            paths.extend(
                audio_io.export_candidates(
                    samples,
                    sample_rate,
                    track,
                    [candidate],
                    destination,
                    file_format=file_format,
                )
            )
        except Exception as exc:  # noqa: BLE001 - preserve successes and expose all writer failures
            return ExportReport(tuple(paths), f"At {candidate.start_seconds:.3f} s: {exc}")
    return ExportReport(tuple(paths))


def export_drag(
    samples: np.ndarray,
    sample_rate: int,
    track: Track,
    candidate: Candidate,
    export_dir: Path,
) -> Path:
    return audio_io.export_candidates(
        samples,
        sample_rate,
        track,
        [candidate],
        export_dir / "dragged",
        file_format="wav",
        subtype="PCM_24",
    )[0]
