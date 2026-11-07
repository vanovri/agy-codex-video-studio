from __future__ import annotations

import pytest

from agy_codex_studio.contracts import TranscriptSegment
from agy_codex_studio.shorts_scorer import (
    _score_boundaries,
    _score_coherence,
    _score_density,
    _score_emotion_and_proof,
    _score_hook,
    score_transcript_segments,
)


@pytest.mark.parametrize(
    ("first_text", "min_expected"),
    [
        ("50 Hz mains hum corrupts EMG", 8.0),
        ("99.5% frame drop rate killed naive parsers", 8.0),  # '%' unit boundary check!
        ("42.47% speculative acceptance proof", 8.0),
        ("100 mV calibration baseline", 5.5),
        ("and maybe something happened", 2.0),
    ],
)
def test_score_hook_recognizes_numbers_units_and_percent_signs(
    first_text: str, min_expected: float
) -> None:
    score = _score_hook(first_text)
    assert min_expected <= score <= 10.0


def test_score_hook_gives_percent_unit_bonus() -> None:
    without_unit = _score_hook("99 apples")
    with_percent = _score_hook("99% accuracy")
    assert with_percent > without_unit


def test_score_density_counts_hyphenated_domain_terms_crc32_and_sha256() -> None:
    baseline = _score_density("generic words without domain terms", duration=14.0)
    with_hashes = _score_density("CRC-32 and SHA-256 packet integrity", duration=14.0)
    # Remove numbers comparison by also testing pure hyphenated/normalized match vs plain number
    only_nums = _score_density("32 and 256 packet integrity", duration=14.0)
    assert with_hashes > only_nums >= baseline


@pytest.mark.parametrize(
    ("full_text", "first_text", "last_text", "expected_min", "expected_max"),
    [
        ("STM32 captures 4000 Hz telemetry cleanly.", "STM32 captures", "cleanly.", 8.5, 10.0),
        ('"STM32 captures 4000 Hz telemetry cleanly."', '"STM32 captures', 'cleanly."', 8.5, 10.0),
        ("and we waited,", "and we", "waited,", 0.0, 2.5),
        ("because it broke;", "because it", "broke;", 0.0, 2.5),
        ("", "", "", 0.0, 4.0),
    ],
)
def test_score_coherence_variations(
    full_text: str,
    first_text: str,
    last_text: str,
    expected_min: float,
    expected_max: float,
) -> None:
    val = _score_coherence(full_text, first_text, last_text)
    assert expected_min <= val <= expected_max


def test_score_transcript_segments_strictly_respects_target_max_sec() -> None:
    segments = [
        TranscriptSegment(id=1, text="50 Hz hum corrupts raw EMG.", start=0.0, end=10.0),
        TranscriptSegment(id=2, text="STM32 captures 4000 Hz DMA.", start=10.2, end=20.0),
        TranscriptSegment(id=3, text="CRC-32 proof locks zero drops.", start=20.2, end=35.0),
    ]
    candidates = score_transcript_segments(segments, target_min_sec=15.0, target_max_sec=25.0)
    assert len(candidates) >= 1
    for c in candidates:
        assert 15.0 <= (c.end - c.start) <= 25.0, (
            f"Candidate [{c.start}, {c.end}] exceeded target_max_sec=25.0"
        )


def test_score_transcript_segments_empty_and_short_fallback() -> None:
    assert score_transcript_segments([]) == []

    short_segs = [
        TranscriptSegment(id=1, text="50 Hz notch verified.", start=0.0, end=4.0),
    ]
    fallback = score_transcript_segments(short_segs, target_min_sec=15.0, target_max_sec=45.0)
    assert len(fallback) == 1
    assert fallback[0].start == 0.0
    assert fallback[0].end == 4.0


@pytest.mark.parametrize(
    ("min_s", "max_s"),
    [
        (0.0, 30.0),
        (-5.0, 30.0),
        (30.0, 15.0),
        (float("nan"), 30.0),
    ],
)
def test_score_transcript_segments_rejects_invalid_bounds(min_s: float, max_s: float) -> None:
    segs = [TranscriptSegment(id=1, text="Test.", start=0.0, end=20.0)]
    with pytest.raises(ValueError):
        score_transcript_segments(segs, target_min_sec=min_s, target_max_sec=max_s)


def test_score_boundaries_pause_snapping() -> None:
    segs = [
        TranscriptSegment(id=1, text="A.", start=0.0, end=5.0),
        TranscriptSegment(id=2, text="B.", start=5.02, end=10.0),  # tight 20ms gap
        TranscriptSegment(id=3, text="C.", start=10.4, end=15.0),  # clean 400ms gap
    ]
    assert _score_boundaries(segs, 0, 2) == 10.0
    assert _score_boundaries(segs, 1, 1) == 7.5  # tight start (2.5) + clean end (5.0)
    assert _score_emotion_and_proof("Zero drops verified deterministic proof captures locks.") == 10.0
