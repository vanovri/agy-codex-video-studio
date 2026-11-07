from __future__ import annotations

import json
from pathlib import Path
import pytest

from agy_codex_studio.caption_engine import (
    _format_srt_time,
    _format_vtt_time,
    build_caption_groups,
    export_captions,
)
from agy_codex_studio.contracts import CaptionGroup, WordTimestamp


@pytest.mark.parametrize(
    ("seconds", "expected_srt", "expected_vtt"),
    [
        (0.0, "00:00:00,000", "00:00:00.000"),
        (-2.5, "00:00:00,000", "00:00:00.000"),
        (0.2, "00:00:00,200", "00:00:00.200"),
        (59.9999, "00:01:00,000", "00:01:00.000"),
        (61.005, "00:01:01,005", "00:01:01.005"),
        (3661.789, "01:01:01,789", "01:01:01.789"),
        (36000.5, "10:00:00,500", "10:00:00.500"),
    ],
)
def test_time_formatters_srt_and_vtt(
    seconds: float, expected_srt: str, expected_vtt: str
) -> None:
    assert _format_srt_time(seconds) == expected_srt
    assert _format_vtt_time(seconds) == expected_vtt


@pytest.mark.parametrize("bad_sec", [float("nan"), float("inf"), float("-inf")])
def test_time_formatters_reject_non_finite_values(bad_sec: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        _format_srt_time(bad_sec)
    with pytest.raises(ValueError, match="finite"):
        _format_vtt_time(bad_sec)


@pytest.mark.parametrize("punct", [".", ",", "!", "?", "—", "–", ":"])
def test_build_caption_groups_breaks_on_every_supported_punctuation(punct: str) -> None:
    words = [
        WordTimestamp("Signal", 0.0, 0.2),
        WordTimestamp(f"locked{punct}", 0.22, 0.5),
        WordTimestamp("Next", 0.55, 0.8),
        WordTimestamp("frame", 0.82, 1.1),
    ]
    groups = build_caption_groups(words, max_words=6, pause_break_sec=0.5)
    assert len(groups) == 2
    assert groups[0].text == f"Signal locked{punct}"
    assert groups[1].text == "Next frame"


@pytest.mark.parametrize("bad_max_words", [0, -1, -10])
def test_build_caption_groups_rejects_non_positive_max_words(bad_max_words: int) -> None:
    words = [WordTimestamp("hello", 0.0, 0.5)]
    with pytest.raises(ValueError, match="max_words"):
        build_caption_groups(words, max_words=bad_max_words)


def test_build_caption_groups_rejects_negative_pause_break() -> None:
    words = [WordTimestamp("hello", 0.0, 0.5)]
    with pytest.raises(ValueError, match="pause_break_sec"):
        build_caption_groups(words, max_words=4, pause_break_sec=-0.01)


def test_build_caption_groups_empty_input() -> None:
    assert build_caption_groups([]) == []
    assert build_caption_groups([WordTimestamp("   ", 0.0, 0.2), WordTimestamp("\t\n", 0.2, 0.4)]) == []
    padded = [
        WordTimestamp("  ", 0.0, 0.1),
        WordTimestamp(" locked. ", 0.1, 0.4),
        WordTimestamp("Next", 0.5, 0.8),
    ]
    groups = build_caption_groups(padded, max_words=4, pause_break_sec=0.5)
    assert [g.text for g in groups] == ["locked.", "Next"]


def test_export_captions_empty_groups_creates_valid_files(tmp_path: Path) -> None:
    paths = export_captions([], tmp_path)
    data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert data["groups"] == []
    assert data["captions"] == []
    assert data["meta"]["group_count"] == 0
    assert data["meta"]["start_sec"] == 0.0
    assert data["meta"]["end_sec"] == 0.0
    vtt = Path(paths["vtt"]).read_text(encoding="utf-8")
    assert vtt.startswith("WEBVTT")


def test_export_captions_sanitizes_cue_breaking_newlines_and_arrows(tmp_path: Path) -> None:
    groups = [
        CaptionGroup(
            id="cg_01",
            text="Line1\n\n00:00:05,000 --> 00:00:09,000\nInjected",
            start=1.0,
            end=2.5,
        ),
        CaptionGroup(
            id="cg_02",
            text="Reversed end",
            start=4.0,
            end=3.0,  # inverted end < start should clamp end >= start
        ),
    ]
    paths = export_captions(groups, tmp_path)
    srt_text = Path(paths["srt"]).read_text(encoding="utf-8")
    vtt_text = Path(paths["vtt"]).read_text(encoding="utf-8")
    json_data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))

    # Only 2 cue timing headers may exist in SRT and VTT
    assert srt_text.count(" --> ") == 2
    assert vtt_text.count(" --> ") == 2
    assert json_data["captions"][1]["endMs"] >= json_data["captions"][1]["startMs"]
