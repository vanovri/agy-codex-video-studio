from __future__ import annotations

import math
import pytest

from agy_codex_studio.contracts import (
    CaptionGroup,
    CutInterval,
    MediaProbeResult,
    ShortCandidate,
    SoundtrackManifest,
    TranscriptSegment,
    WordTimestamp,
)


@pytest.mark.parametrize(
    ("word", "start", "end", "score", "expected_start", "expected_end", "expected_score"),
    [
        ("STM32", 0.1 + 0.2, 0.9004, 0.98765, 0.3, 0.9, 0.988),
        ("DMA", 0.0, 0.1256, 1.0, 0.0, 0.126, 1.0),
        ("CRC-32", 12.3456, 12.7894, 0.5, 12.346, 12.789, 0.5),
        ("mV", 35.9999, 36.0001, 0.0, 36.0, 36.0, 0.0),
    ],
)
def test_word_timestamp_rounds_floats_deterministically(
    word: str,
    start: float,
    end: float,
    score: float,
    expected_start: float,
    expected_end: float,
    expected_score: float,
) -> None:
    wt = WordTimestamp(word=word, start=start, end=end, score=score)
    d = wt.to_dict()
    assert d == {
        "word": word,
        "start": expected_start,
        "end": expected_end,
        "score": expected_score,
    }


@pytest.mark.parametrize(
    ("bad_start", "bad_end", "bad_score"),
    [
        (float("nan"), 1.0, 1.0),
        (0.0, float("inf"), 1.0),
        (float("-inf"), 1.0, 1.0),
        (0.0, 1.0, float("nan")),
    ],
)
def test_word_timestamp_rejects_non_finite_floats_on_serialization(
    bad_start: float, bad_end: float, bad_score: float
) -> None:
    wt = WordTimestamp(word="x", start=bad_start, end=bad_end, score=bad_score)
    with pytest.raises(ValueError, match="finite"):
        wt.to_dict()


@pytest.mark.parametrize(
    ("start", "end", "expected_duration"),
    [
        (1.0, 2.5, 1.5),
        (2.5, 2.5, 0.0),
        (3.0, 1.0, 0.0),  # inverted interval clamps duration to 0.0
        (0.1 + 0.2, 0.7, 0.4),
    ],
)
def test_cut_interval_duration_calculation(
    start: float, end: float, expected_duration: float
) -> None:
    ci = CutInterval(start=start, end=end, reason="silence")
    out = ci.to_dict()
    assert out["duration"] == expected_duration
    assert out["reason"] == "silence"


def test_contracts_to_dict_returns_defensive_copies() -> None:
    cg = CaptionGroup(id="cg_1", text="hello", start=0.0, end=1.0)
    cg_dict = cg.to_dict()
    cg_dict["safe_box"]["x"] = -999
    assert cg.safe_box["x"] == 90

    sc = ShortCandidate(
        start=0.0,
        end=20.0,
        score=8.5,
        hook_strength=9.0,
        standalone_coherence=8.0,
        emotional_intensity=8.0,
        information_density=8.5,
        natural_boundaries=9.0,
        text="STM32 test.",
        breakdown={"hook_strength": 9.0},
    )
    sc_dict = sc.to_dict()
    sc_dict["breakdown"]["hook_strength"] = 0.0
    assert sc.breakdown["hook_strength"] == 9.0

    mp = MediaProbeResult(
        file="a.mp4",
        width=1920,
        height=1080,
        fps=29.97002997,
        duration_sec=24.0004,
        video_codec="h264",
        audio_codec="aac",
        has_audio=True,
        file_size_bytes=512,
        raw={"streams": [{"index": 0}]},
    )
    mp_dict = mp.to_dict()
    assert mp_dict["fps"] == 29.97
    assert mp_dict["duration_sec"] == 24.0
    mp_dict["raw"]["streams"].append({"index": 1})
    assert len(mp.raw["streams"]) == 1

    sm = SoundtrackManifest(
        file="s.wav",
        duration_sec=12.0,
        sample_rate=48000,
        channels=2,
        bpm=120.0,
        beats=[0.0, 0.5004],
        scene_cues={"scene_1": {"t_start": 0.0}},
        peak_dbfs=-1.612,
        rms_dbfs=-14.389,
    )
    sm_dict = sm.to_dict()
    assert sm_dict["beats"] == [0.0, 0.5]
    sm_dict["scene_cues"]["scene_1"]["t_start"] = 999.0
    assert sm.scene_cues["scene_1"]["t_start"] == 0.0


def test_transcript_segment_nested_word_rounding() -> None:
    seg = TranscriptSegment(
        id="seg_01",
        text="50 Hz",
        start=0.1 + 0.2,
        end=1.2345,
        words=[WordTimestamp("50", 0.1 + 0.2, 0.6), WordTimestamp("Hz", 0.65, 1.2345)],
    )
    out = seg.to_dict()
    assert out["start"] == 0.3
    assert out["end"] == 1.234
    assert out["words"][0]["start"] == 0.3
    assert out["words"][1]["end"] == 1.234
