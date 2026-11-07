from __future__ import annotations

from pathlib import Path
import wave
import numpy as np
import pytest

from agy_codex_studio.soundtrack_synth import (
    synthesize_showcase_soundtrack,
    synthesize_soundtrack_pcm,
)


@pytest.mark.parametrize(
    ("duration_sec", "bpm", "expected_beats"),
    [
        (1.0, 120.0, 2),
        (4.0, 60.0, 4),
        (6.0, 120.0, 12),
        (29.5, 120.0, 59),
    ],
)
def test_synthesize_soundtrack_pcm_in_memory_without_disk_io(
    duration_sec: float, bpm: float, expected_beats: int
) -> None:
    buf = synthesize_soundtrack_pcm(duration_sec=duration_sec, bpm=bpm, sample_rate=8000)
    assert buf["interleaved_pcm"].shape == (int(duration_sec * 8000), 2)
    assert buf["interleaved_pcm"].dtype == np.int16
    assert len(buf["beats"]) == expected_beats
    assert buf["peak_dbfs"] <= -1.50
    assert -24.0 <= buf["rms_dbfs"] <= -10.0


@pytest.mark.parametrize(
    ("bad_duration", "bad_bpm", "bad_sr"),
    [
        (0.0, 120.0, 48000),
        (-3.0, 120.0, 48000),
        (5.0, 0.0, 48000),
        (5.0, -90.0, 48000),
        (5.0, 120.0, 0),
        (float("nan"), 120.0, 48000),
        (5.0, float("inf"), 48000),
    ],
)
def test_synthesize_soundtrack_rejects_invalid_dsp_parameters(
    tmp_path: Path, bad_duration: float, bad_bpm: float, bad_sr: int
) -> None:
    with pytest.raises(ValueError):
        synthesize_soundtrack_pcm(
            duration_sec=bad_duration, bpm=bad_bpm, sample_rate=bad_sr
        )
    if bad_sr == 48000:
        with pytest.raises(ValueError):
            synthesize_showcase_soundtrack(
                tmp_path / "bad.wav", duration_sec=bad_duration, bpm=bad_bpm
            )


def test_synthesize_showcase_soundtrack_determinism(tmp_path: Path) -> None:
    w1 = tmp_path / "a.wav"
    w2 = tmp_path / "b.wav"
    m1 = synthesize_showcase_soundtrack(w1, duration_sec=2.0, bpm=120.0)
    m2 = synthesize_showcase_soundtrack(w2, duration_sec=2.0, bpm=120.0)
    assert w1.read_bytes() == w2.read_bytes()
    assert m1.peak_dbfs == m2.peak_dbfs
    assert m1.rms_dbfs == m2.rms_dbfs
    with wave.open(str(w1), "rb") as wf:
        assert wf.getnframes() == 96000
