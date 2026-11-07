from __future__ import annotations

import pytest

from agy_codex_studio.contracts import WordTimestamp
from agy_codex_studio.ghost_trimmer import FILLER_WORDS, detect_and_trim_words


@pytest.mark.parametrize("filler", sorted(FILLER_WORDS))
def test_every_filler_word_is_detected_case_and_punctuation_insensitively(filler: str) -> None:
    words = [
        WordTimestamp("Start", 0.0, 0.3),
        WordTimestamp(f"{filler.upper()},", 0.35, 0.65),
        WordTimestamp("End", 0.70, 1.0),
    ]
    res = detect_and_trim_words(words)
    assert res["removed_fillers"] == 1
    assert [w.word for w in res["kept_words"]] == ["Start", "End"]


def test_empty_word_list_returns_zeroed_structure() -> None:
    res = detect_and_trim_words([])
    assert res == {
        "kept_words": [],
        "cut_intervals": [],
        "removed_fillers": 0,
        "saved_seconds": 0.0,
        "remapped_words": [],
    }


def test_lead_silence_trimmed_when_first_word_delayed() -> None:
    words = [WordTimestamp("Delayed", 2.0, 2.5)]
    res = detect_and_trim_words(words, max_pause_sec=0.35, pad_start_sec=0.1)
    assert len(res["cut_intervals"]) == 1
    assert res["cut_intervals"][0].reason == "lead_silence"
    assert res["cut_intervals"][0].start == 0.0
    assert res["cut_intervals"][0].end == pytest.approx(1.9)
    assert res["remapped_words"][0].start == pytest.approx(0.1)


def test_overlapping_asr_filler_never_causes_remapped_word_inversion() -> None:
    # Real Whisper edge case: filler slightly overlaps trailing edge of preceding word
    words = [
        WordTimestamp("Hello", 0.0, 0.50),
        WordTimestamp("um", 0.45, 0.80),
        WordTimestamp("world", 0.80, 1.20),
    ]
    res = detect_and_trim_words(words)
    remapped = res["remapped_words"]
    assert len(remapped) == 2
    assert remapped[0].end <= remapped[1].start, (
        f"Timeline inversion: {remapped[0]} overlaps {remapped[1]}"
    )


def test_rapid_short_words_do_not_overlap_after_remapping() -> None:
    words = [
        WordTimestamp("a", 0.00, 0.02),
        WordTimestamp("b", 0.03, 0.06),
        WordTimestamp("c", 0.07, 0.12),
    ]
    res = detect_and_trim_words(words)
    remapped = res["remapped_words"]
    for i in range(len(remapped) - 1):
        assert remapped[i].end <= remapped[i + 1].start


def test_punctuation_only_tokens_do_not_trigger_false_retake_pruning() -> None:
    # "..." + "Hello" vs "?" + "Hello" only shares 1 real word ("Hello"), NOT a 2-word retake!
    words = [
        WordTimestamp("...", 1.0, 1.1),
        WordTimestamp("Hello", 1.1, 1.4),
        WordTimestamp("team", 1.5, 1.8),
        WordTimestamp("?", 2.0, 2.1),
        WordTimestamp("Hello", 2.1, 2.4),
        WordTimestamp("again", 2.5, 2.8),
    ]
    res = detect_and_trim_words(words)
    kept = [w.word for w in res["kept_words"]]
    assert "team" in kept


def test_retake_beyond_eight_second_window_is_preserved() -> None:
    words = [
        WordTimestamp("We", 0.0, 0.2),
        WordTimestamp("verified", 0.25, 0.6),
        WordTimestamp("STM32", 0.7, 1.1),
        # > 8.0s later: legitimate callback / refrain, not an aborted retake
        WordTimestamp("We", 10.0, 10.2),
        WordTimestamp("verified", 10.25, 10.6),
        WordTimestamp("ENVIID", 10.7, 11.1),
    ]
    res = detect_and_trim_words(words, max_pause_sec=20.0)
    assert len(res["kept_words"]) == 6


@pytest.mark.parametrize(
    ("max_pause", "pad_start", "pad_end"),
    [
        (-0.1, 0.08, 0.12),
        (0.35, -0.05, 0.12),
        (0.35, 0.08, -0.05),
        (float("nan"), 0.08, 0.12),
    ],
)
def test_detect_and_trim_words_rejects_invalid_parameters(
    max_pause: float, pad_start: float, pad_end: float
) -> None:
    words = [WordTimestamp("ok", 0.0, 0.5)]
    with pytest.raises(ValueError):
        detect_and_trim_words(
            words,
            max_pause_sec=max_pause,
            pad_start_sec=pad_start,
            pad_end_sec=pad_end,
        )
