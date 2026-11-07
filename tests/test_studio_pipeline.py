from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path
import pytest
import numpy as np

from agy_codex_studio.contracts import (
    CaptionGroup,
    CutInterval,
    MediaProbeResult,
    ShortCandidate,
    SoundtrackManifest,
    TranscriptSegment,
    WordTimestamp,
)
from agy_codex_studio.ghost_trimmer import (
    FILLER_WORDS,
    detect_and_trim_words,
)
from agy_codex_studio.caption_engine import (
    build_caption_groups,
    export_captions,
)
from agy_codex_studio.shorts_scorer import (
    score_transcript_segments,
)
from agy_codex_studio.soundtrack_synth import (
    synthesize_showcase_soundtrack,
)
from agy_codex_studio.ffmpeg_bridge import (
    probe_media,
    run_ffmpeg_skill,
)
from agy_codex_studio.cli import (
    cmd_doctor,
    cmd_generate_showcase_assets,
)
from agy_codex_studio.quad_showcase import (
    QUAD_SCENES_SPEC,
    QuadShowcaseRenderer,
    build_quad_caption_groups,
    get_quad_showcase_words,
)
from agy_codex_studio.hackathon_demos import (
    BENCHMIND_SCENES_SPEC,
    REDFLAG_SCENES_SPEC,
    BenchMindHackathonRenderer,
    RedFlagLoopHackathonRenderer,
    build_scene_caption_groups,
)


def test_contracts_dataclasses_and_serialization():
    wt = WordTimestamp(word="STM32", start=0.5, end=0.9, score=0.98)
    assert wt.to_dict()["word"] == "STM32"

    seg = TranscriptSegment(id=1, text="STM32 captures 4000 Hz", start=0.5, end=2.0, words=[wt])
    d_seg = seg.to_dict()
    assert d_seg["id"] == 1
    assert len(d_seg["words"]) == 1

    cg = CaptionGroup(id="cg_01", text="50 Hz mains hum", start=0.2, end=2.4)
    d_cg = cg.to_dict()
    assert d_cg["id"] == "cg_01"
    assert "safe_box" in d_cg

    cut = CutInterval(start=1.0, end=1.5, reason="silence")
    assert cut.to_dict()["duration"] == 0.5

    sc = ShortCandidate(
        start=0.0,
        end=36.0,
        score=9.15,
        hook_strength=9.5,
        standalone_coherence=8.8,
        emotional_intensity=8.5,
        information_density=9.2,
        natural_boundaries=9.0,
        text="Sample candidate",
    )
    assert sc.to_dict()["score"] == 9.15

    mp = MediaProbeResult(
        file="test.mp4",
        width=1080,
        height=1920,
        fps=30.0,
        duration_sec=36.0,
        video_codec="h264",
        audio_codec="aac",
        has_audio=True,
        file_size_bytes=1048576,
    )
    assert mp.to_dict()["fps"] == 30.0

    sm = SoundtrackManifest(
        file="track.wav",
        duration_sec=36.0,
        sample_rate=48000,
        channels=2,
        bpm=120.0,
        beats=[0.0, 0.5, 1.0],
        scene_cues={"scene_1": {"t_start": 0.0}},
        peak_dbfs=-1.8,
        rms_dbfs=-14.2,
    )
    assert sm.to_dict()["bpm"] == 120.0


def test_ghost_trimmer_removes_fillers():
    words = [
        WordTimestamp("um", 0.0, 0.4),
        WordTimestamp("The", 0.5, 0.8),
        WordTimestamp("uh", 0.9, 1.2),
        WordTimestamp("system", 1.3, 1.8),
        WordTimestamp("anu", 1.9, 2.2),
        WordTimestamp("works", 2.3, 2.8),
        WordTimestamp("eh", 2.9, 3.2),
    ]
    res = detect_and_trim_words(words)
    assert res["removed_fillers"] == 4
    kept_words = [w.word for w in res["kept_words"]]
    assert kept_words == ["The", "system", "works"]
    assert res["saved_seconds"] > 0.0


def test_ghost_trimmer_compresses_pauses():
    words = [
        WordTimestamp("Signal", 0.1, 0.5),
        # 1.5s silence gap between 0.5 and 2.0
        WordTimestamp("processed", 2.0, 2.5),
    ]
    res = detect_and_trim_words(words, max_pause_sec=0.35, pad_start_sec=0.08, pad_end_sec=0.12)
    # Pause is 1.5s, cut should be from 0.5 + 0.12 = 0.62 to 2.0 - 0.08 = 1.92 (1.3s cut)
    silence_cuts = [c for c in res["cut_intervals"] if "silence" in c.reason]
    assert len(silence_cuts) >= 1
    assert res["saved_seconds"] >= 1.2
    assert res["remapped_words"][1].start < 2.0


def test_ghost_trimmer_detects_repeated_retakes():
    words = [
        # First aborted attempt
        WordTimestamp("We", 0.5, 0.7),
        WordTimestamp("measured", 0.8, 1.2),
        # Fluent second take within 8 seconds
        WordTimestamp("We", 2.0, 2.2),
        WordTimestamp("measured", 2.3, 2.7),
        WordTimestamp("the", 2.8, 3.0),
        WordTimestamp("impedance", 3.1, 3.8),
    ]
    res = detect_and_trim_words(words)
    kept_texts = [w.word for w in res["kept_words"]]
    # Should keep only the later take
    assert kept_texts == ["We", "measured", "the", "impedance"]
    retake_cuts = [c for c in res["cut_intervals"] if "retake" in c.reason]
    assert len(retake_cuts) == 1


def test_caption_engine_build_groups_word_limit():
    words = [WordTimestamp(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(10)]
    groups = build_caption_groups(words, max_words=4)
    assert len(groups) == 3
    assert len(groups[0].words) == 4
    assert len(groups[1].words) == 4
    assert len(groups[2].words) == 2


def test_caption_engine_build_groups_punctuation_and_pause():
    words = [
        WordTimestamp("50", 0.1, 0.3),
        WordTimestamp("Hz.", 0.35, 0.6),  # punctuation break
        WordTimestamp("Mains", 0.7, 0.9),
        WordTimestamp("hum", 0.95, 1.2),
        # pause break: gap from 1.2 to 1.6 = 0.4s >= 0.22s
        WordTimestamp("killed", 1.6, 2.0),
    ]
    groups = build_caption_groups(words, max_words=5, pause_break_sec=0.22)
    assert len(groups) >= 3
    assert groups[0].text == "50 Hz."


def test_caption_engine_export_captions_files(tmp_path: Path):
    groups = [
        CaptionGroup(id="cg_01", text="50 Hz mains hum", start=0.2, end=2.4),
        CaptionGroup(id="cg_02", text="STM32 captures 4000 Hz", start=2.5, end=5.0),
    ]
    paths = export_captions(groups, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["srt"]).exists()
    assert Path(paths["vtt"]).exists()

    with open(paths["json"], "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data["groups"]) == 2
        assert len(data["captions"]) == 2
        assert data["captions"][0]["text"] == "50 Hz mains hum"

    with open(paths["srt"], "r", encoding="utf-8") as f:
        content = f.read()
        assert "00:00:00,200 --> 00:00:02,400" in content

    with open(paths["vtt"], "r", encoding="utf-8") as f:
        content = f.read()
        assert content.startswith("WEBVTT")


def test_shorts_scorer_weights_and_dimensions():
    segments = [
        TranscriptSegment(
            id=1,
            text="50 Hz mains hum corrupts raw surface EMG signals.",
            start=0.0,
            end=5.0,
        ),
        TranscriptSegment(
            id=2,
            text="STM32 captures 4,000 Hz via DMA and locks DC baseline.",
            start=5.0,
            end=12.0,
        ),
        TranscriptSegment(
            id=3,
            text="Cascaded Butterworth biquad carves a -25.5 dB notch canyon.",
            start=12.0,
            end=20.0,
        ),
    ]
    candidates = score_transcript_segments(segments, target_min_sec=15.0, target_max_sec=30.0)
    assert len(candidates) >= 1
    best = candidates[0]
    assert 0.0 <= best.score <= 10.0
    for dim in [
        "hook_strength",
        "standalone_coherence",
        "emotional_intensity",
        "information_density",
        "natural_boundaries",
    ]:
        assert dim in best.breakdown
        assert 0.0 <= best.breakdown[dim] <= 10.0


def test_shorts_scorer_sorts_by_score():
    segments = [
        TranscriptSegment(id=1, text="and then we looked at it maybe,", start=0.0, end=8.0),
        TranscriptSegment(id=2, text="so we saw some weird numbers.", start=8.0, end=16.0),
        TranscriptSegment(id=3, text="STM32 captures 4,000 Hz with -25.5 dB notch filter proof.", start=16.0, end=26.0),
        TranscriptSegment(id=4, text="12,043 rows zero drops verified deterministic ledger.", start=26.0, end=36.0),
    ]
    candidates = score_transcript_segments(segments, target_min_sec=15.0, target_max_sec=25.0)
    assert len(candidates) >= 2
    for i in range(len(candidates) - 1):
        assert candidates[i].score >= candidates[i + 1].score


def test_soundtrack_synth_generates_valid_wav(tmp_path: Path):
    wav_path = tmp_path / "test_synth.wav"
    manifest = synthesize_showcase_soundtrack(wav_path, duration_sec=5.0, bpm=120.0)

    assert wav_path.exists()
    assert manifest.sample_rate == 48000
    assert manifest.channels == 2
    assert manifest.peak_dbfs <= -1.50
    assert manifest.rms_dbfs < -10.0

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000
        assert wf.getnframes() == int(5.0 * 48000)


def test_soundtrack_synth_silence_break_and_cues(tmp_path: Path):
    wav_path = tmp_path / "test_36s.wav"
    manifest = synthesize_showcase_soundtrack(wav_path, duration_sec=36.0, bpm=120.0)

    assert "scene_1" in manifest.scene_cues
    assert "pre_payoff_break" in manifest.scene_cues
    assert "scene_5" in manifest.scene_cues
    assert len(manifest.beats) == 72  # 36.0s / 0.5s

    # Verify audio at 28.6s is silent (< -60 dBFS)
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        wf.setpos(int(28.6 * sr))
        frames = wf.readframes(int(0.2 * sr))
        samples = np.frombuffer(frames, dtype=np.int16)
        max_amp = np.max(np.abs(samples))
        assert max_amp < 100  # near absolute zero digital silence


def test_ffmpeg_bridge_probe_wav(tmp_path: Path):
    wav_path = tmp_path / "probe_test.wav"
    synthesize_showcase_soundtrack(wav_path, duration_sec=3.0, bpm=120.0)

    probe = probe_media(wav_path)
    assert probe.has_audio is True
    assert probe.duration_sec >= 2.9
    assert probe.file_size_bytes > 0


def test_ffmpeg_bridge_run_skill():
    res = run_ffmpeg_skill("_contract", ["doctor"])
    assert isinstance(res, dict)
    assert "ok" in res or "available" in res


def test_cli_doctor():
    args = argparse.Namespace(json=True)
    code = cmd_doctor(args)
    assert code == 0


def test_cli_generate_showcase_assets(tmp_path: Path):
    args = argparse.Namespace(out_dir=str(tmp_path), duration=36.0)
    code = cmd_generate_showcase_assets(args)
    assert code == 0

    assert (tmp_path / "soundtrack.wav").exists()
    assert (tmp_path / "captions.json").exists()
    assert (tmp_path / "captions.srt").exists()
    assert (tmp_path / "captions.vtt").exists()
    assert (tmp_path / "studio_manifest.json").exists()

    with open(tmp_path / "studio_manifest.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["verified_metrics"]["adc_rate_hz"] == 4000
        assert data["verified_metrics"]["telemetry_rows"] == 12043
        assert len(data["captions"]["groups"]) == 10


def test_quad_showcase_scenes_and_frame_renderer():
    assert len(QUAD_SCENES_SPEC) == 4
    words = get_quad_showcase_words()
    assert len(words) > 20
    groups = build_quad_caption_groups()
    assert len(groups) == 8
    assert groups[0].start == 0.15
    assert groups[-1].end == 23.85

    renderer = QuadShowcaseRenderer()
    for sample_frame in [0, 90, 210, 390, 570, 719]:
        img = renderer.render_frame(sample_frame)
        assert img.size == (1080, 1920)
        assert img.mode == "RGB"

    out_dir = Path(r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs")
    mp4_file = out_dir / "ardhya-engineering-quad-showcase-1080x1920.mp4"
    json_file = out_dir / "ardhya-engineering-quad-showcase.json"
    srt_file = out_dir / "ardhya-engineering-quad-showcase.srt"
    assert mp4_file.exists()
    assert json_file.exists()
    assert srt_file.exists()


def test_benchmind_hackathon_widescreen_demo_verified():
    assert len(BENCHMIND_SCENES_SPEC) == 4
    groups = build_scene_caption_groups(BENCHMIND_SCENES_SPEC, "benchmind")
    assert len(groups) == 8

    renderer = BenchMindHackathonRenderer()
    for f_idx in [0, 90, 240, 420, 600, 719]:
        img = renderer.render_frame(f_idx)
        assert img.size == (1920, 1080)
        assert img.mode == "RGB"

    out_dir = Path(r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs")
    mp4_file = out_dir / "benchmind-v02-hackathon-demo-1920x1080.mp4"
    sheet_file = out_dir / "benchmind-v02-hackathon-demo-1920x1080_sheet.png"
    srt_file = out_dir / "benchmind-v02-hackathon-demo-1920x1080.srt"
    json_file = out_dir / "benchmind-v02-hackathon-demo-1920x1080.json"

    assert mp4_file.exists()
    assert sheet_file.exists() and sheet_file.stat().st_size > 1024
    assert srt_file.exists() and "1,997/1,997" in srt_file.read_text(encoding="utf-8")
    assert json_file.exists()

    probe = probe_media(mp4_file)
    assert probe.width == 1920
    assert probe.height == 1080
    assert abs(probe.fps - 30.0) < 0.2
    assert 23.8 <= probe.duration_sec <= 24.2
    assert probe.video_codec == "h264"
    assert probe.has_audio is True
    assert probe.audio_codec == "aac"


def test_redflag_loop_hackathon_widescreen_demo_verified():
    assert len(REDFLAG_SCENES_SPEC) == 4
    groups = build_scene_caption_groups(REDFLAG_SCENES_SPEC, "redflag")
    assert len(groups) == 8

    renderer = RedFlagLoopHackathonRenderer()
    for f_idx in [0, 90, 240, 420, 600, 719]:
        img = renderer.render_frame(f_idx)
        assert img.size == (1920, 1080)
        assert img.mode == "RGB"

    out_dir = Path(r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs")
    mp4_file = out_dir / "redflag-loop-sea-codex-demo-1920x1080.mp4"
    sheet_file = out_dir / "redflag-loop-sea-codex-demo-1920x1080_sheet.png"
    srt_file = out_dir / "redflag-loop-sea-codex-demo-1920x1080.srt"
    json_file = out_dir / "redflag-loop-sea-codex-demo-1920x1080.json"

    assert mp4_file.exists()
    assert sheet_file.exists() and sheet_file.stat().st_size > 1024
    assert srt_file.exists() and "1.000" in srt_file.read_text(encoding="utf-8")
    assert json_file.exists()

    probe = probe_media(mp4_file)
    assert probe.width == 1920
    assert probe.height == 1080
    assert abs(probe.fps - 30.0) < 0.2
    assert 23.8 <= probe.duration_sec <= 24.2
    assert probe.video_codec == "h264"
    assert probe.has_audio is True
    assert probe.audio_codec == "aac"


