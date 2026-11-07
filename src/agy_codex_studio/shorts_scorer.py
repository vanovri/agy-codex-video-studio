from __future__ import annotations

import math
import re
from typing import Dict, List, Set

from .contracts import ShortCandidate, TranscriptSegment

TECHNICAL_DOMAIN_TERMS: Set[str] = {
    "stm32",
    "adc",
    "dma",
    "emg",
    "biquad",
    "butterworth",
    "notch",
    "filter",
    "hpf",
    "lpf",
    "rms",
    "mav",
    "pearson",
    "crc-32",
    "sha-256",
    "enviid",
    "mrv",
    "telemetry",
    "biochar",
    "frequency",
    "signalproof",
    "linearity",
    "samples",
    "attenuation",
    "mains",
    "hum",
}

_NORMALIZED_DOMAIN_TERMS: Set[str] = TECHNICAL_DOMAIN_TERMS | {
    re.sub(r"[^\w]", "", term).lower() for term in TECHNICAL_DOMAIN_TERMS
}

PATTERN_INTERRUPT_WORDS: Set[str] = {
    "corrupts",
    "corrupt",
    "killed",
    "kills",
    "lock",
    "locks",
    "proof",
    "zero",
    "drops",
    "never",
    "real",
    "truth",
    "secret",
    "break",
    "versus",
    "stop",
}

IMPACT_VERBS: Set[str] = {
    "captures",
    "carves",
    "climbs",
    "stamps",
    "nulls",
    "eliminates",
    "filters",
    "locks",
    "measures",
}

VERIFICATION_WORDS: Set[str] = {
    "verified",
    "verification",
    "deterministic",
    "ledger",
    "guarantee",
    "proof",
    "zero drops",
    "linearity",
    "calibrated",
    "exact",
}

DANGLING_CONNECTORS: Set[str] = {
    "and",
    "or",
    "but",
    "so",
    "because",
    "then",
    "he",
    "she",
    "it",
    "they",
}

_UNIT_PATTERN = re.compile(
    r"(?:(?<=\d)\s*|(?<!\w))(?:khz|hz|db|mv|ms|v|w)(?!\w)|(?<=\d)\s*%",
    re.IGNORECASE,
)

_LEADING_WRAP_CHARS = "\"'“”‘’([{<"
_TRAILING_WRAP_CHARS = "\"'“”‘’)]}>"


def _score_hook(first_text: str) -> float:
    score = 2.0
    if re.search(r"\d+", first_text):
        score += 2.5
    if _UNIT_PATTERN.search(first_text):
        score += 2.0
    tokens = {re.sub(r"[^\w]", "", t).lower() for t in first_text.split()}
    if tokens & PATTERN_INTERRUPT_WORDS:
        score += 2.5
    first_word = first_text.split()[0] if first_text.split() else ""
    first_clean = re.sub(r"[^\w]", "", first_word).lower()
    if first_clean and first_clean not in DANGLING_CONNECTORS:
        score += 1.0
    return min(10.0, max(0.0, score))


def _score_coherence(text: str, first_text: str, last_text: str) -> float:
    score = 2.0
    first_word = first_text.split()[0] if first_text.split() else ""
    first_stripped = first_word.lstrip(_LEADING_WRAP_CHARS)
    first_clean = re.sub(r"[^\w]", "", first_stripped).lower()

    if first_stripped and (first_stripped[0].isupper() or first_stripped[0].isdigit()):
        score += 2.5
    if first_clean in DANGLING_CONNECTORS:
        score -= 2.0
    elif first_clean:
        score += 1.5

    last_stripped = last_text.strip().rstrip(_TRAILING_WRAP_CHARS)
    last_char = last_stripped[-1] if last_stripped else ""
    if last_char in {".", "!", "?"}:
        score += 3.0
    elif last_char in {",", ";", "-"}:
        score -= 1.0

    if len(text.split()) >= 6:
        score += 1.0

    return min(10.0, max(0.0, score))


def _score_emotion_and_proof(text: str) -> float:
    score = 2.0
    lower_text = text.lower()
    tokens = {re.sub(r"[^\w]", "", t) for t in lower_text.split()}

    if tokens & PATTERN_INTERRUPT_WORDS:
        score += 2.5
    if tokens & IMPACT_VERBS:
        score += 2.5
    if tokens & {w.lower() for w in VERIFICATION_WORDS} or "zero drops" in lower_text:
        score += 3.0

    return min(10.0, max(0.0, score))


def _score_density(text: str, duration: float) -> float:
    domain_hits = 0
    for raw_tok in text.split():
        hyphen_kept = re.sub(r"^[^\w]+|[^\w]+$", "", raw_tok).lower()
        alnum_only = re.sub(r"[^\w]", "", raw_tok).lower()
        if (hyphen_kept and hyphen_kept in _NORMALIZED_DOMAIN_TERMS) or (
            alnum_only and alnum_only in _NORMALIZED_DOMAIN_TERMS
        ):
            domain_hits += 1

    num_hits = len(re.findall(r"\d+", text))
    total_metrics = domain_hits + num_hits

    rate = (total_metrics / max(1.0, duration)) * 14.0
    return min(10.0, max(1.0, rate))


def _score_boundaries(
    segments: List[TranscriptSegment], i: int, j: int
) -> float:
    score = 0.0
    if i == 0:
        score += 5.0
    else:
        prev_gap = segments[i].start - segments[i - 1].end
        score += 5.0 if prev_gap >= 0.15 else 2.5

    if j == len(segments) - 1:
        score += 5.0
    else:
        next_gap = segments[j + 1].start - segments[j].end
        score += 5.0 if next_gap >= 0.15 else 2.5

    return min(10.0, max(0.0, score))


def score_transcript_segments(
    segments: List[TranscriptSegment],
    target_min_sec: float = 15.0,
    target_max_sec: float = 45.0,
) -> List[ShortCandidate]:
    """Score candidate sub-segments across 5 weighted dimensions and return sorted candidates."""
    if (
        isinstance(target_min_sec, bool)
        or isinstance(target_max_sec, bool)
        or not isinstance(target_min_sec, (int, float))
        or not isinstance(target_max_sec, (int, float))
        or not math.isfinite(target_min_sec)
        or not math.isfinite(target_max_sec)
        or target_min_sec <= 0.0
        or target_max_sec < target_min_sec
    ):
        raise ValueError(
            f"Invalid duration bounds: target_min_sec={target_min_sec!r}, target_max_sec={target_max_sec!r}"
        )

    if not segments:
        return []

    for idx, seg in enumerate(segments):
        if (
            isinstance(seg.start, bool)
            or isinstance(seg.end, bool)
            or not isinstance(seg.start, (int, float))
            or not isinstance(seg.end, (int, float))
            or not math.isfinite(seg.start)
            or not math.isfinite(seg.end)
        ):
            raise ValueError(f"Segment at index {idx} has non-finite timestamps: {seg!r}")

    candidates: List[ShortCandidate] = []
    n = len(segments)

    for i in range(n):
        for j in range(i, n):
            seg_start = segments[i].start
            seg_end = segments[j].end
            duration = seg_end - seg_start

            if duration < target_min_sec or duration > target_max_sec:
                continue

            window_segs = segments[i : j + 1]
            full_text = " ".join(s.text.strip() for s in window_segs if s.text.strip())
            first_text = window_segs[0].text.strip()
            last_text = window_segs[-1].text.strip()

            hook = _score_hook(first_text)
            coherence = _score_coherence(full_text, first_text, last_text)
            emotion = _score_emotion_and_proof(full_text)
            density = _score_density(full_text, duration)
            boundaries = _score_boundaries(segments, i, j)

            total_score = (
                0.30 * hook
                + 0.25 * coherence
                + 0.20 * emotion
                + 0.15 * density
                + 0.10 * boundaries
            )
            total_score = min(10.0, max(0.0, total_score))

            breakdown: Dict[str, float] = {
                "hook_strength": round(hook, 2),
                "standalone_coherence": round(coherence, 2),
                "emotional_intensity": round(emotion, 2),
                "information_density": round(density, 2),
                "natural_boundaries": round(boundaries, 2),
            }

            candidates.append(
                ShortCandidate(
                    start=round(seg_start, 3),
                    end=round(seg_end, 3),
                    score=round(total_score, 2),
                    hook_strength=round(hook, 2),
                    standalone_coherence=round(coherence, 2),
                    emotional_intensity=round(emotion, 2),
                    information_density=round(density, 2),
                    natural_boundaries=round(boundaries, 2),
                    text=full_text,
                    breakdown=breakdown,
                )
            )

    if not candidates:
        seg_start = segments[0].start
        seg_end = max(seg_start, segments[-1].end)
        dur = max(0.1, seg_end - seg_start)
        full_text = " ".join(s.text.strip() for s in segments if s.text.strip())
        hook = _score_hook(segments[0].text.strip())
        coherence = _score_coherence(
            full_text, segments[0].text.strip(), segments[-1].text.strip()
        )
        emotion = _score_emotion_and_proof(full_text)
        density = _score_density(full_text, dur)
        boundaries = 8.0
        total_score = min(
            10.0,
            max(
                0.0,
                0.30 * hook
                + 0.25 * coherence
                + 0.20 * emotion
                + 0.15 * density
                + 0.10 * boundaries,
            ),
        )
        candidates.append(
            ShortCandidate(
                start=round(seg_start, 3),
                end=round(seg_end, 3),
                score=round(total_score, 2),
                hook_strength=round(hook, 2),
                standalone_coherence=round(coherence, 2),
                emotional_intensity=round(emotion, 2),
                information_density=round(density, 2),
                natural_boundaries=round(boundaries, 2),
                text=full_text,
                breakdown={
                    "hook_strength": round(hook, 2),
                    "standalone_coherence": round(coherence, 2),
                    "emotional_intensity": round(emotion, 2),
                    "information_density": round(density, 2),
                    "natural_boundaries": round(boundaries, 2),
                },
            )
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates
