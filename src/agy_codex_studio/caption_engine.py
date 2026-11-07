from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from .contracts import CaptionGroup, WordTimestamp

PUNCTUATION_BREAKS = {".", ",", "!", "?", "—", "–", ":"}


def _require_finite(value: Union[int, float], name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return float(value)


def _format_srt_time(sec: float) -> str:
    val = _require_finite(sec, "sec")
    total_ms = int(round(max(0.0, val) * 1000))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_vtt_time(sec: float) -> str:
    val = _require_finite(sec, "sec")
    total_ms = int(round(max(0.0, val) * 1000))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def sanitize_cue_text(text: str, *, escape_vtt_arrows: bool = False) -> str:
    """Prevent embedded blank lines or cue-timing arrows from corrupting SRT/WebVTT blocks."""
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    non_empty_lines = [ln.strip() for ln in normalized.split("\n") if ln.strip()]
    cleaned = "\n".join(non_empty_lines) if non_empty_lines else ""
    if escape_vtt_arrows:
        cleaned = cleaned.replace("-->", "--&gt;")
    else:
        cleaned = cleaned.replace("-->", "->")
    return cleaned


def _normalized_bounds(g: CaptionGroup) -> Tuple[float, float]:
    s = max(0.0, _require_finite(g.start, "CaptionGroup.start"))
    e = max(s, _require_finite(g.end, "CaptionGroup.end"))
    return s, e


def build_caption_groups(
    words: List[WordTimestamp],
    max_words: int = 4,
    pause_break_sec: float = 0.22,
) -> List[CaptionGroup]:
    """Group word timestamps into 2-5 word phrases breaking on punctuation or pauses."""
    if isinstance(max_words, bool) or not isinstance(max_words, int) or max_words < 1:
        raise ValueError(f"max_words must be an integer >= 1, got {max_words!r}")
    pause_val = _require_finite(pause_break_sec, "pause_break_sec")
    if pause_val < 0.0:
        raise ValueError(f"pause_break_sec must be >= 0.0, got {pause_break_sec!r}")

    if not words:
        return []

    for w in words:
        _require_finite(w.start, "WordTimestamp.start")
        _require_finite(w.end, "WordTimestamp.end")

    cleaned_words: List[WordTimestamp] = [
        WordTimestamp(word=str(w.word).strip(), start=w.start, end=w.end, score=w.score)
        for w in words
        if str(w.word).strip()
    ]
    if not cleaned_words:
        return []

    groups: List[CaptionGroup] = []
    current_words: List[WordTimestamp] = []
    group_idx = 1

    for i, w in enumerate(cleaned_words):
        current_words.append(w)
        ends_with_punct = any(w.word.endswith(p) for p in PUNCTUATION_BREAKS)
        pause_ahead = False
        if i < len(cleaned_words) - 1:
            if cleaned_words[i + 1].start - w.end >= pause_val:
                pause_ahead = True

        should_break = (
            len(current_words) >= max_words
            or ends_with_punct
            or pause_ahead
            or (i == len(cleaned_words) - 1)
        )

        if should_break:
            grp_id = f"cg_{group_idx:02d}"
            text = " ".join(item.word for item in current_words)
            start_t = max(0.0, current_words[0].start)
            end_t = max(start_t, current_words[-1].end)
            groups.append(
                CaptionGroup(
                    id=grp_id,
                    text=text,
                    start=start_t,
                    end=end_t,
                    words=list(current_words),
                )
            )
            group_idx += 1
            current_words = []

    return groups


def build_captions_payload(groups: List[CaptionGroup]) -> Dict[str, Any]:
    """Construct pure in-memory JSON caption dictionary (HyperFrames + Remotion schema)."""
    normalized_pairs = [_normalized_bounds(g) for g in groups]
    return {
        "groups": [
            {
                **g.to_dict(),
                "start": round(s, 3),
                "end": round(e, 3),
            }
            for g, (s, e) in zip(groups, normalized_pairs)
        ],
        "captions": [
            {
                "text": g.text,
                "startMs": int(round(s * 1000)),
                "endMs": int(round(e * 1000)),
            }
            for g, (s, e) in zip(groups, normalized_pairs)
        ],
        "meta": {
            "group_count": len(groups),
            "start_sec": round(normalized_pairs[0][0], 3) if normalized_pairs else 0.0,
            "end_sec": round(normalized_pairs[-1][1], 3) if normalized_pairs else 0.0,
            "safe_box": {"x": 90, "y": 1180, "width": 900, "height": 150},
        },
    }


def format_srt_document(groups: List[CaptionGroup]) -> str:
    """Render deterministic SubRip (.srt) document text."""
    if not groups:
        return ""
    srt_blocks: List[str] = []
    for idx, g in enumerate(groups, start=1):
        s, e = _normalized_bounds(g)
        s_str = _format_srt_time(s)
        e_str = _format_srt_time(e)
        body = sanitize_cue_text(g.text, escape_vtt_arrows=False)
        srt_blocks.append(f"{idx}\n{s_str} --> {e_str}\n{body}")
    return "\n\n".join(srt_blocks) + "\n"


def format_vtt_document(groups: List[CaptionGroup]) -> str:
    """Render deterministic WebVTT (.vtt) document text."""
    if not groups:
        return "WEBVTT\n"
    vtt_blocks: List[str] = ["WEBVTT"]
    for idx, g in enumerate(groups, start=1):
        s, e = _normalized_bounds(g)
        s_str = _format_vtt_time(s)
        e_str = _format_vtt_time(e)
        body = sanitize_cue_text(g.text, escape_vtt_arrows=True)
        vtt_blocks.append(f"{idx}\n{s_str} --> {e_str}\n{body}")
    return "\n\n".join(vtt_blocks) + "\n"


def export_captions(
    groups: List[CaptionGroup],
    out_dir: Union[str, Path],
) -> Dict[str, str]:
    """Write captions.json (HyperFrames + Remotion), captions.srt, and captions.vtt."""
    target_dir = Path(out_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    json_file = target_dir / "captions.json"
    srt_file = target_dir / "captions.srt"
    vtt_file = target_dir / "captions.vtt"

    json_data = build_captions_payload(groups)
    srt_text = format_srt_document(groups)
    vtt_text = format_vtt_document(groups)

    json_file.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
    srt_file.write_text(srt_text, encoding="utf-8")
    vtt_file.write_text(vtt_text, encoding="utf-8")

    return {
        "json": str(json_file),
        "srt": str(srt_file),
        "vtt": str(vtt_file),
    }
