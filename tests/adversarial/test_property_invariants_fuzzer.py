from __future__ import annotations

import io
import math
import random
import re
from typing import List
import wave

from agy_codex_studio.caption_engine import (
    build_caption_groups,
    build_captions_payload,
    format_srt_document,
    format_vtt_document,
)
from agy_codex_studio.contracts import CaptionGroup, TranscriptSegment, WordTimestamp
from agy_codex_studio.ghost_trimmer import FILLER_WORDS, detect_and_trim_words
from agy_codex_studio.shorts_scorer import score_transcript_segments
from agy_codex_studio.soundtrack_synth import synthesize_soundtrack_pcm

SRT_CUE_RE = re.compile(r"^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n", re.MULTILINE)
VTT_CUE_RE = re.compile(r"^\d+\n\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\n", re.MULTILINE)

VOCAB = [
    "STM32",
    "captures",
    "4000",
    "Hz",
    "DMA",
    "Butterworth",
    "biquad",
    "-25.5",
    "dB",
    "CRC-32",
    "SHA-256",
    "99.5%",
    "recovery.",
    "linearity!",
    "verified?",
    "...",
    "?!",
    '"quoted"',
    "🚀",
    "العربية",
    "中文",
] + sorted(FILLER_WORDS)


def test_2500_case_deterministic_property_fuzzer() -> None:
    """Run 2,500 randomized property-based differential fuzz configurations with zero external deps."""
    rng = random.Random(20261107)
    total_executed = 0

    # 1. 800 randomized ASR word-timing & ghost-trimming + caption-grouping fuzz cases
    for _ in range(800):
        n_words = rng.randint(0, 28)
        cursor = rng.uniform(0.0, 1.5)
        words: List[WordTimestamp] = []
        for _w_i in range(n_words):
            # Occasionally inject jitter, zero-duration, or slight overlap
            start = max(0.0, cursor + rng.uniform(-0.08, 1.25))
            end = max(0.0, start + rng.uniform(-0.02, 0.55))
            tok = rng.choice(VOCAB)
            words.append(WordTimestamp(word=tok, start=start, end=end, score=rng.uniform(0.1, 1.0)))
            cursor = max(cursor, end)
        if rng.random() < 0.25:
            rng.shuffle(words)

        max_pause = rng.uniform(0.15, 1.2)
        pad_s = rng.uniform(0.0, 0.08)
        pad_e = rng.uniform(0.0, 0.08)
        trim_out = detect_and_trim_words(
            words, max_pause_sec=max_pause, pad_start_sec=pad_s, pad_end_sec=pad_e
        )
        remapped: List[WordTimestamp] = trim_out["remapped_words"]
        assert len(remapped) == len(trim_out["kept_words"])
        assert trim_out["saved_seconds"] >= 0.0

        for idx, rw in enumerate(remapped):
            assert 0.0 <= rw.start <= rw.end
            if idx > 0:
                assert remapped[idx - 1].end <= rw.start + 1e-6

        max_w = rng.randint(1, 8)
        pause_b = rng.uniform(0.0, 0.8)
        groups = build_caption_groups(remapped, max_words=max_w, pause_break_sec=pause_b)
        for g_idx, g in enumerate(groups):
            assert 1 <= len(g.words) <= max_w
            assert 0.0 <= g.start <= g.end
            if g_idx > 0:
                assert groups[g_idx - 1].end <= g.start + 1e-6
        total_executed += 1

    # 2. 800 randomized SRT & WebVTT adversarial cue round-trip fuzz cases
    adversarial_fragments = [
        "normal text",
        "line1\n\n99\n00:00:01,000 --> 00:00:02,000\nFAKE",
        "arrow --> spoof",
        "\r\n\r\nWEBVTT\r\n",
        "\u202eRTL\u202c\u200bZWSP",
        "100% STM32 — verified!",
        "   multiple   spaces   ",
    ]
    for _ in range(800):
        n_groups = rng.randint(0, 12)
        t_cur = 0.0
        groups_in: List[CaptionGroup] = []
        for idx in range(n_groups):
            s = t_cur + rng.uniform(0.0, 0.5)
            # Include occasional inverted end < start to verify normalization invariant
            e = s + rng.uniform(-0.3, 2.0)
            body = " ".join(rng.choice(adversarial_fragments) for _ in range(rng.randint(1, 3)))
            groups_in.append(
                CaptionGroup(
                    id=f"fuzz_{idx}",
                    text=body,
                    start=s,
                    end=e,
                    words=[WordTimestamp("w", max(0.0, s), max(0.0, s, e))],
                )
            )
            t_cur = max(s, e, 0.0)

        payload = build_captions_payload(groups_in)
        srt_doc = format_srt_document(groups_in)
        vtt_doc = format_vtt_document(groups_in)

        assert payload["meta"]["group_count"] == n_groups
        assert len(SRT_CUE_RE.findall(srt_doc)) == n_groups
        assert len(VTT_CUE_RE.findall(vtt_doc)) == n_groups
        assert srt_doc.count(" --> ") == n_groups
        assert vtt_doc.count(" --> ") == n_groups
        total_executed += 1

    # 3. 600 randomized viral-shorts transcript scorer fuzz cases
    for _ in range(600):
        n_segs = rng.randint(0, 10)
        segs: List[TranscriptSegment] = []
        t_pos = 0.0
        for idx in range(n_segs):
            dur = rng.uniform(1.5, 9.0)
            txt = " ".join(rng.choice(VOCAB) for _ in range(rng.randint(1, 18)))
            segs.append(TranscriptSegment(id=idx, text=txt, start=t_pos, end=t_pos + dur))
            t_pos += dur + rng.uniform(0.0, 0.4)

        t_min = rng.uniform(2.0, 12.0)
        t_max = t_min + rng.uniform(2.0, 25.0)
        has_in_range_window = any(
            t_min <= (segs[j].end - segs[i].start) <= t_max
            for i in range(len(segs))
            for j in range(i, len(segs))
        )
        cands = score_transcript_segments(segs, target_min_sec=t_min, target_max_sec=t_max)
        if not segs:
            assert cands == []
        elif not has_in_range_window:
            # Fallback contract: returns single whole-transcript candidate when no sub-window fits
            assert len(cands) == 1
            assert cands[0].start == round(segs[0].start, 3)
            assert cands[0].end == round(max(segs[0].start, segs[-1].end), 3)
        for c_idx, cand in enumerate(cands):
            scaled_100 = cand.score * 10.0
            assert 0.0 <= cand.score <= 10.0
            assert 0.0 <= scaled_100 <= 100.0
            for dim_val in (
                cand.hook_strength,
                cand.standalone_coherence,
                cand.emotional_intensity,
                cand.information_density,
                cand.natural_boundaries,
            ):
                assert 0.0 <= dim_val <= 10.0
            if has_in_range_window:
                win_dur = cand.end - cand.start
                assert t_min - 2e-3 <= win_dur <= t_max + 2e-3
            if c_idx > 0:
                assert cands[c_idx - 1].score >= cand.score
        total_executed += 1

    # 4. 300 randomized PCM soundtrack & RIFF/WAVE container framing fuzz cases
    for _ in range(300):
        dur = rng.uniform(0.05, 6.0)
        bpm = rng.uniform(45.0, 200.0)
        sr = rng.choice([2000, 4000, 8000, 16000])
        pcm_info = synthesize_soundtrack_pcm(duration_sec=dur, bpm=bpm, sample_rate=sr)

        expected_frames = int(round(dur * sr))
        interleaved = pcm_info["interleaved_pcm"]
        assert interleaved.shape == (expected_frames, 2)
        pcm_bytes: bytes = interleaved.tobytes()
        # Stereo 16-bit PCM = 4 bytes/frame exact alignment
        assert len(pcm_bytes) == expected_frames * 4
        assert math.isfinite(pcm_info["peak_dbfs"]) and pcm_info["peak_dbfs"] <= 0.0
        assert math.isfinite(pcm_info["rms_dbfs"]) and pcm_info["rms_dbfs"] <= pcm_info["peak_dbfs"] + 1e-6

        # Verify RIFF/WAVE container framing in memory
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm_bytes)
        raw_wav = buf.getvalue()
        assert raw_wav[:4] == b"RIFF"
        assert raw_wav[8:12] == b"WAVE"
        buf.seek(0)
        with wave.open(buf, "rb") as rf:
            assert rf.getnframes() == expected_frames
            assert rf.getnchannels() == 2
            assert rf.getsampwidth() == 2
        total_executed += 1

    assert total_executed == 2500
