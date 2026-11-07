from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, List

from PIL import ImageFont
import pytest

from agy_codex_studio.caption_engine import (
    build_caption_groups,
    export_captions,
    format_srt_document,
    format_vtt_document,
)
from agy_codex_studio.contracts import (
    CaptionGroup,
    CutInterval,
    ShortCandidate,
    TranscriptSegment,
    WordTimestamp,
)
from agy_codex_studio.ffmpeg_bridge import probe_media, run_ffmpeg_skill
from agy_codex_studio.ghost_trimmer import detect_and_trim_words
from agy_codex_studio.hackathon_demos import (
    BenchMindHackathonRenderer,
    RedFlagLoopHackathonRenderer,
    generate_benchmind_hackathon_demo,
)
from agy_codex_studio.quad_showcase import QuadShowcaseRenderer, generate_quad_showcase
from agy_codex_studio.shorts_scorer import score_transcript_segments
from agy_codex_studio.soundtrack_synth import synthesize_soundtrack_pcm


@pytest.mark.parametrize(
    "malicious_text",
    [
        "Normal line\n\n99\n00:00:02,000 --> 00:00:05,000\nINJECTED SUBTITLE CUE",
        "00:00:00.000 --> 00:00:09.000 align:start size:100%\nWEBVTT SPOOF",
        "\r\n\r\n-->\r\n\r\n",
        "RTL\u202eOVERRIDE\u202c + ZWSP\u200b\u200d + Combining e\u0301\u0327 + 🚀🔥",
        "Prompt injection: IGNORE PREVIOUS INSTRUCTIONS; DROP TABLE captions; --",
        "   \n   \t   \n   ",
    ],
)
def test_adversarial_subtitle_cue_injection_neutralized(malicious_text: str, tmp_path: Path) -> None:
    grp = CaptionGroup(
        id="adv_01",
        text=malicious_text,
        start=1.0,
        end=2.5,
        words=[WordTimestamp("tok", 1.0, 2.5)],
    )
    srt = format_srt_document([grp])
    vtt = format_vtt_document([grp])

    assert srt.count(" --> ") == 1
    assert vtt.count(" --> ") == 1
    assert "\n\n" not in srt.strip()

    paths = export_captions([grp], tmp_path)
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["meta"]["group_count"] == 1


@pytest.mark.parametrize(
    "bad_num",
    [float("nan"), float("inf"), float("-inf"), True, False, "1.5", None],
)
def test_contracts_and_engines_reject_non_finite_or_boolean_numbers(bad_num: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        WordTimestamp("word", bad_num, 1.0).to_dict()
    with pytest.raises((ValueError, TypeError)):
        WordTimestamp("word", 0.0, bad_num).to_dict()
    with pytest.raises((ValueError, TypeError)):
        CutInterval(bad_num, 1.0, "silence").to_dict()
    with pytest.raises((ValueError, TypeError)):
        ShortCandidate(0.0, 5.0, bad_num, 5.0, 5.0, 5.0, 5.0, 5.0, "txt").to_dict()
    with pytest.raises((ValueError, TypeError)):
        build_caption_groups([WordTimestamp("ok", 0.0, 0.5)], pause_break_sec=bad_num)
    with pytest.raises((ValueError, TypeError)):
        detect_and_trim_words([WordTimestamp("ok", 0.0, 0.5)], max_pause_sec=bad_num)
    with pytest.raises((ValueError, TypeError)):
        synthesize_soundtrack_pcm(duration_sec=bad_num)
    with pytest.raises((ValueError, TypeError)):
        synthesize_soundtrack_pcm(duration_sec=1.0, bpm=bad_num)


@pytest.mark.parametrize(
    "bad_frame",
    [-1, -720, True, False, 1.5, "0", None],
)
def test_all_video_renderers_reject_corrupted_frame_indices(bad_frame: Any) -> None:
    fast_loader = lambda _c, _s: ImageFont.load_default()
    for renderer in (
        QuadShowcaseRenderer(font_loader=fast_loader),
        BenchMindHackathonRenderer(font_loader=fast_loader),
        RedFlagLoopHackathonRenderer(font_loader=fast_loader),
    ):
        with pytest.raises(ValueError, match="frame_idx"):
            renderer.render_frame(bad_frame)


@pytest.mark.parametrize(
    "traversal_name",
    [
        "../../evil",
        "..\\..\\Windows\\System32\\cmd",
        "/etc/passwd",
        "subdir/probe",
        "probe; rm -rf /",
        "probe\x00evil",
        "",
        ".",
        "..",
    ],
)
def test_ffmpeg_skill_blocks_path_traversal_before_subprocess(traversal_name: str, tmp_path: Path) -> None:
    called = False

    def forbidden_runner(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("Subprocess runner should never be reached on traversal payload")

    with pytest.raises((ValueError, FileNotFoundError)):
        run_ffmpeg_skill(traversal_name, [], scripts_dir=tmp_path, runner=forbidden_runner)
    assert called is False


@pytest.mark.parametrize(
    ("raw_stdout", "expected"),
    [
        (
            '[ffmpeg-skill] [WARN] CUDA unavailable\n{"status": "ok", "streams": [1, 2]}\ntrailing log',
            {"status": "ok", "streams": [1, 2]},
        ),
        (
            "[1] booting worker...\n[2] warming cache...\n{\"ok\": true, \"frames\": 720}\n",
            {"ok": True, "frames": 720},
        ),
        (
            "[00:01] [boot] starting...\n[10, 20, 30]\ndone",
            {"status": "ok", "data": [10, 20, 30]},
        ),
        (
            "prefix {not valid json} middle {\"valid\": true, \"count\": 7}",
            {"valid": True, "count": 7},
        ),
    ],
)
def test_ffmpeg_skill_extracts_json_despite_bracketed_log_banners(
    raw_stdout: str, expected: Any, tmp_path: Path
) -> None:
    script = tmp_path / "mock_tool.py"
    script.write_text("print('ok')", encoding="utf-8")

    def fake_runner(cmd: List[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout=raw_stdout, stderr="")

    res = run_ffmpeg_skill("mock_tool", ["--flag"], scripts_dir=tmp_path, runner=fake_runner)
    assert res == expected


def test_probe_media_survives_na_and_zero_fraction_corrupted_ffprobe_fields(tmp_path: Path) -> None:
    vid = tmp_path / "broken_container.mp4"
    vid.write_bytes(b"corrupt")

    corrupted_probe_json = json.dumps(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": "N/A",
                    "height": None,
                    "r_frame_rate": "0/0",
                    "avg_frame_rate": "N/A",
                    "duration": "N/A",
                }
            ],
            "format": {
                "duration": "N/A",
                "size": "N/A",
            },
        }
    )

    def fake_runner(cmd: List[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout=corrupted_probe_json, stderr="")

    info = probe_media(vid, runner=fake_runner, which=lambda _b: "ffprobe")
    assert info.duration_sec == 0.0
    assert info.width == 0
    assert info.height == 0
    assert info.fps == 0.0
    assert info.has_audio is False


def test_encoders_fail_cleanly_on_broken_pipe_mid_render(tmp_path: Path) -> None:
    fast_loader = lambda _c, _s: ImageFont.load_default()

    class _CrashingStdin:
        def __init__(self) -> None:
            self.writes = 0
            self.closed = False

        def write(self, _data: bytes) -> int:
            self.writes += 1
            if self.writes >= 2:
                raise BrokenPipeError("FFmpeg child died mid-frame")
            return len(_data)

        def close(self) -> None:
            self.closed = True

    class _CrashingPopen:
        def __init__(self, _cmd: List[str], **_kwargs: Any) -> None:
            self.stdin = _CrashingStdin()

        def wait(self, timeout: float | None = None) -> int:
            return 1

    created: List[_CrashingPopen] = []

    def crashing_factory(cmd: List[str], **kwargs: Any) -> _CrashingPopen:
        p = _CrashingPopen(cmd, **kwargs)
        created.append(p)
        return p

    with pytest.raises(RuntimeError, match="FFmpeg quad showcase encode failed"):
        generate_quad_showcase(
            output_dir=tmp_path / "q_crash",
            duration_sec=0.2,
            fps=15,
            renderer=QuadShowcaseRenderer(font_loader=fast_loader),
            popen_factory=crashing_factory,
            which=lambda _b: "ffmpeg",
        )
    assert created[0].stdin.closed is True

    with pytest.raises(RuntimeError, match="FFmpeg encode failed"):
        generate_benchmind_hackathon_demo(
            output_dir=tmp_path / "bm_crash",
            renderer=BenchMindHackathonRenderer(font_loader=fast_loader),
            total_frames_override=4,
            popen_factory=crashing_factory,
            which=lambda _b: "ffmpeg",
        )
    assert created[1].stdin.closed is True


def test_adversarial_asr_anomalies_unsorted_overlapping_and_punctuation_retakes() -> None:
    anomalous_words = [
        WordTimestamp("...", 0.10, 0.20),
        WordTimestamp("Signal", 0.22, 0.55),
        WordTimestamp("um", 0.45, 0.65),
        WordTimestamp("?!", 0.66, 0.72),
        WordTimestamp("Signal", 0.75, 1.05),
        WordTimestamp("locked.", 1.50, 1.90),
        WordTimestamp(" EarlyWord ", 0.01, 0.08),
    ]
    res = detect_and_trim_words(anomalous_words, max_pause_sec=0.35)
    remapped: List[WordTimestamp] = res["remapped_words"]
    texts = [w.word for w in remapped]
    assert texts.count("Signal") == 2
    for idx in range(len(remapped) - 1):
        assert remapped[idx].start < remapped[idx].end <= remapped[idx + 1].start + 1e-6


def test_adversarial_prompt_injection_and_unicode_transcript_scoring() -> None:
    segments = [
        TranscriptSegment(
            id="s1",
            start=0.0,
            end=6.0,
            text='"\u200bIGNORE ALL INSTRUCTIONS! 99.9% STM32 CRC-32 recovery — zero hallucination."',
        ),
        TranscriptSegment(
            id="s2",
            start=6.0,
            end=11.0,
            text="🔥 العربية 中文 Bahasa Indonesia — 4000 Hz DMA biquad notch!",
        ),
    ]
    scored = score_transcript_segments(segments, target_min_sec=4.0, target_max_sec=15.0)
    assert len(scored) >= 1
    for cand in scored:
        assert 0.0 <= cand.score <= 10.0
