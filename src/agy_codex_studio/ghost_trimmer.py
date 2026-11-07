from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Set

from .contracts import CutInterval, WordTimestamp

FILLER_WORDS: Set[str] = {
    "um",
    "uh",
    "er",
    "ah",
    "hmm",
    "uhm",
    "erm",
    "anu",
    "eee",
    "eh",
}


def _clean_token(w: str) -> str:
    return re.sub(r"[^\w]", "", str(w)).lower()


def _require_non_negative_finite(val: float, name: str) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0.0:
        raise ValueError(f"{name} must be a finite number >= 0.0, got {val!r}")
    return float(val)


def _merge_cut_intervals(intervals: List[CutInterval]) -> List[CutInterval]:
    valid = [c for c in intervals if c.end > c.start]
    if not valid:
        return []
    sorted_int = sorted(valid, key=lambda x: (x.start, x.end))
    merged: List[CutInterval] = []

    cur_start = sorted_int[0].start
    cur_end = sorted_int[0].end
    reasons = {sorted_int[0].reason} if sorted_int[0].reason else set()

    for item in sorted_int[1:]:
        if item.start <= cur_end + 1e-4:
            cur_end = max(cur_end, item.end)
            if item.reason:
                reasons.add(item.reason)
        else:
            merged.append(CutInterval(cur_start, cur_end, reason=";".join(sorted(reasons))))
            cur_start = item.start
            cur_end = item.end
            reasons = {item.reason} if item.reason else set()

    merged.append(CutInterval(cur_start, cur_end, reason=";".join(sorted(reasons))))
    return [m for m in merged if m.end > m.start]


def _remap_point(t: float, merged_cuts: List[CutInterval]) -> float:
    """Monotonically map original timestamp t onto the post-cut timeline."""
    removed = 0.0
    for cut in merged_cuts:
        if cut.start >= t:
            break
        removed += max(0.0, min(t, cut.end) - cut.start)
    return max(0.0, t - removed)


def detect_and_trim_words(
    words: List[WordTimestamp],
    max_pause_sec: float = 0.35,
    pad_start_sec: float = 0.08,
    pad_end_sec: float = 0.12,
) -> Dict[str, Any]:
    """Detect filler words, repeated retakes, and compress pauses beyond max_pause_sec."""
    max_pause = _require_non_negative_finite(max_pause_sec, "max_pause_sec")
    pad_start = _require_non_negative_finite(pad_start_sec, "pad_start_sec")
    pad_end = _require_non_negative_finite(pad_end_sec, "pad_end_sec")

    if not words:
        return {
            "kept_words": [],
            "cut_intervals": [],
            "removed_fillers": 0,
            "saved_seconds": 0.0,
            "remapped_words": [],
        }

    # Validate & normalize chronological ordering without mutating caller objects
    normalized_words: List[WordTimestamp] = []
    for idx_in, w in enumerate(words):
        if (
            isinstance(w.start, bool)
            or isinstance(w.end, bool)
            or not isinstance(w.start, (int, float))
            or not isinstance(w.end, (int, float))
            or not math.isfinite(w.start)
            or not math.isfinite(w.end)
        ):
            raise ValueError(f"WordTimestamp at index {idx_in} has non-finite bounds: {w!r}")
        s_clamp = max(0.0, float(w.start))
        e_clamp = max(s_clamp, float(w.end))
        normalized_words.append(WordTimestamp(word=w.word, start=s_clamp, end=e_clamp, score=w.score))

    ordered_words = [
        item[1]
        for item in sorted(enumerate(normalized_words), key=lambda pair: (pair[1].start, pair[0]))
    ]

    raw_cuts: List[CutInterval] = []

    # 1. Detect repeated retakes (phrases of length 2-5 repeated within 8 seconds)
    cleaned_tokens = [_clean_token(w.word) for w in ordered_words]
    n = len(ordered_words)
    retake_indices: Set[int] = set()

    for i in range(n):
        if i in retake_indices:
            continue
        for k in range(min(5, n - i), 1, -1):
            phrase_1 = cleaned_tokens[i : i + k]
            # Every token in a repeated retake prefix must be an actual word (not empty punctuation)
            if not all(phrase_1):
                continue
            found_match_j = -1
            for j in range(i + k, n):
                if ordered_words[j].start - ordered_words[i].start > 8.0:
                    break
                if cleaned_tokens[j : j + k] == phrase_1:
                    found_match_j = j
                    break

            if found_match_j != -1:
                for idx in range(i, found_match_j):
                    retake_indices.add(idx)
                raw_cuts.append(
                    CutInterval(
                        start=ordered_words[i].start,
                        end=ordered_words[found_match_j].start,
                        reason="retake",
                    )
                )
                break

    # 2. Filter out retakes and standalone filler words
    kept_words: List[WordTimestamp] = []
    removed_fillers = 0

    for idx, w in enumerate(ordered_words):
        if idx in retake_indices:
            continue
        cleaned = _clean_token(w.word)
        if cleaned in FILLER_WORDS:
            removed_fillers += 1
            raw_cuts.append(CutInterval(start=w.start, end=w.end, reason="filler"))
        else:
            kept_words.append(w)

    # 3. Compress inter-word silences > max_pause between kept words
    for i in range(len(kept_words) - 1):
        w1 = kept_words[i]
        w2 = kept_words[i + 1]
        pause = w2.start - w1.end
        if pause > max_pause:
            cut_start = w1.end + pad_end
            cut_end = w2.start - pad_start
            if cut_end > cut_start:
                raw_cuts.append(CutInterval(start=cut_start, end=cut_end, reason="silence"))

    # If first kept word starts after a gap
    if kept_words and kept_words[0].start > max_pause:
        lead_cut_end = max(0.0, kept_words[0].start - pad_start)
        if lead_cut_end > 0.0:
            raw_cuts.append(CutInterval(start=0.0, end=lead_cut_end, reason="lead_silence"))

    # 4. Merge overlapping cuts
    merged_cuts = _merge_cut_intervals(raw_cuts)
    total_saved_seconds = sum(c.end - c.start for c in merged_cuts)

    # 5. Monotonically remap timestamps of kept words without creating overlaps
    mapped_bounds = [
        (_remap_point(w.start, merged_cuts), _remap_point(w.end, merged_cuts))
        for w in kept_words
    ]
    remapped_words: List[WordTimestamp] = []
    prev_end = 0.0

    for idx, (w, (m_start, m_end)) in enumerate(zip(kept_words, mapped_bounds)):
        new_start = round(max(prev_end, m_start), 3)
        raw_dur = max(0.0, m_end - m_start)
        desired_end = new_start + max(0.05, raw_dur)

        if idx + 1 < len(mapped_bounds):
            next_mapped_start = round(mapped_bounds[idx + 1][0], 3)
            if next_mapped_start >= new_start:
                desired_end = min(desired_end, next_mapped_start)

        new_end = round(max(new_start, desired_end), 3)
        prev_end = new_end
        remapped_words.append(
            WordTimestamp(
                word=w.word,
                start=new_start,
                end=new_end,
                score=w.score,
            )
        )

    return {
        "kept_words": kept_words,
        "cut_intervals": merged_cuts,
        "removed_fillers": removed_fillers,
        "saved_seconds": round(total_saved_seconds, 4),
        "remapped_words": remapped_words,
    }
