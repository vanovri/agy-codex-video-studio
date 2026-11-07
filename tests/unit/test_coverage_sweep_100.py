from __future__ import annotations

import argparse
from pathlib import Path
import runpy
import subprocess
import sys
from typing import Any, List

from PIL import ImageFont
import pytest

from agy_codex_studio import cli as cli_mod
from agy_codex_studio.cli import _first_line, cmd_verify_render, inspect_environment
from agy_codex_studio.contracts import TranscriptSegment, WordTimestamp
from agy_codex_studio.ffmpeg_bridge import (
    _ensure_within_base_dir,
    _find_python,
    _parse_frame_rate,
    extract_contact_sheet,
    probe_media,
    run_ffmpeg_skill,
)
from agy_codex_studio.ghost_trimmer import detect_and_trim_words
from agy_codex_studio.hackathon_demos import (
    BenchMindHackathonRenderer,
    generate_benchmind_hackathon_demo,
)
from agy_codex_studio.quad_showcase import QuadShowcaseRenderer, generate_quad_showcase
from agy_codex_studio.shorts_scorer import score_transcript_segments
from agy_codex_studio.soundtrack_synth import synthesize_soundtrack_pcm


def test_cli_uncovered_error_branches_and_entrypoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _first_line(None) == ""
    assert _first_line("") == ""
    assert _first_line("\n\n") == ""

    def raising_runner(_cmd: List[str], **_kwargs: Any) -> Any:
        raise RuntimeError("binary crashed")

    report = inspect_environment(
        which=lambda name: f"C:/fake/{name}.exe",
        runner=raising_runner,
        skill_runner=lambda _s, _a: {"version": "1.0", "ok": True},
        whisper_checker=lambda: "1.0.0",
    )
    assert report["all_ok"] is False
    assert report["ffmpeg"]["status"] == "error"
    assert report["ffprobe"]["status"] == "error"
    assert report["yt_dlp"]["status"] == "error"
    assert report["hyperframes"]["status"] == "error"

    for bad_dur in (0.0, -5.0, float("nan"), float("inf")):
        ns = argparse.Namespace(mp4_path=str(tmp_path / "x.mp4"), expected_duration=bad_dur, out_dir="")
        with pytest.raises(ValueError, match="expected_duration"):
            cmd_verify_render(ns)

    # Cover cli.main() -> sys.exit(run_cli())
    monkeypatch.setattr(cli_mod, "run_cli", lambda argv=None: 0)
    with pytest.raises(SystemExit) as exc_info:
        cli_mod.main()
    assert exc_info.value.code == 0

    # Cover `if __name__ == "__main__": main()` guard via runpy.run_module
    monkeypatch.setattr(sys, "argv", ["agy-codex-studio", "--help"])
    saved_cli_mod = sys.modules.pop("agy_codex_studio.cli", None)
    try:
        with pytest.raises(SystemExit) as help_exit:
            runpy.run_module("agy_codex_studio.cli", run_name="__main__", alter_sys=True)
        assert help_exit.value.code == 0
    finally:
        if saved_cli_mod is not None:
            sys.modules["agy_codex_studio.cli"] = saved_cli_mod


def test_ffmpeg_bridge_uncovered_fallbacks_and_guards(tmp_path: Path) -> None:
    assert _find_python(None, py314_path=tmp_path / "nonexistent_python.exe") == sys.executable
    assert _parse_frame_rate(None) == 0.0
    assert _parse_frame_rate(True) == 0.0

    with pytest.raises(ValueError, match="path traversal blocked"):
        _ensure_within_base_dir(tmp_path.parent / "evil.py", tmp_path, "evil")

    # Top-level JSON list output in run_ffmpeg_skill
    list_script = tmp_path / "list_out.py"
    list_script.write_text("print('[1, 2]')", encoding="utf-8")
    res_list = run_ffmpeg_skill(
        "list_out",
        scripts_dir=tmp_path,
        runner=lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 0, stdout="[1, 2, 3]", stderr=""),
    )
    assert res_list == {"status": "ok", "data": [1, 2, 3]}

    # probe_media when fallback ffprobe raises OSError
    media_file = tmp_path / "clip.mp4"
    media_file.write_bytes(b"0000")

    def oserror_runner(_cmd: List[str], **_kw: Any) -> Any:
        raise OSError("ffprobe executable missing")

    res_oserr = probe_media(media_file, scripts_dir=tmp_path, runner=oserror_runner, which=lambda _b: None)
    assert res_oserr.video_codec == "none"
    assert "probe failed:" in res_oserr.raw["error"]

    # probe_media when fallback ffprobe returns malformed JSON with exit code 0
    res_bad_json = probe_media(
        media_file,
        scripts_dir=tmp_path,
        runner=lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 0, stdout="{broken-json", stderr=""),
        which=lambda _b: "ffprobe",
    )
    assert res_bad_json.video_codec == "none"
    assert res_bad_json.raw == {"error": "probe failed"}

    # extract_contact_sheet early return when look.py writes non-empty PNG
    look_script = tmp_path / "look.py"
    look_script.write_text("", encoding="utf-8")
    out_sheet = tmp_path / "sheet_ok.png"

    def look_success_runner(cmd: List[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        out_sheet.write_bytes(b"\x89PNG\r\n\x1a\nOK")
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": true}', stderr="")

    returned_sheet = extract_contact_sheet(
        media_file, out_sheet, cols=2, rows=2, scripts_dir=tmp_path, runner=look_success_runner
    )
    assert returned_sheet == out_sheet.resolve()


def test_ghost_trimmer_and_shorts_scorer_non_finite_element_guards() -> None:
    with pytest.raises(ValueError, match="non-finite bounds"):
        detect_and_trim_words([WordTimestamp("bad", float("nan"), 1.0)])

    with pytest.raises(ValueError, match="non-finite timestamps"):
        score_transcript_segments([TranscriptSegment("s1", "text", float("nan"), 5.0)])


def test_quad_and_hackathon_generators_pipe_edge_cases(tmp_path: Path) -> None:
    fast_loader = lambda _c, _s: ImageFont.load_default()

    with pytest.raises(ValueError, match="Invalid duration_sec"):
        generate_quad_showcase(output_dir=tmp_path, duration_sec=0.0, fps=30)

    with pytest.raises(ValueError, match="total_frames must be >= 1"):
        generate_benchmind_hackathon_demo(output_dir=tmp_path, total_frames_override=0)

    class _NullStdinPopen:
        def __init__(self, _cmd: List[str], **_kw: Any) -> None:
            self.stdin = None

    with pytest.raises(RuntimeError, match="without writable stdin"):
        generate_quad_showcase(
            output_dir=tmp_path / "q_nostdin",
            duration_sec=0.1,
            fps=10,
            renderer=QuadShowcaseRenderer(font_loader=fast_loader),
            popen_factory=_NullStdinPopen,
            which=lambda _b: "ffmpeg",
        )

    with pytest.raises(RuntimeError, match="without writable stdin"):
        generate_benchmind_hackathon_demo(
            output_dir=tmp_path / "bm_nostdin",
            renderer=BenchMindHackathonRenderer(font_loader=fast_loader),
            total_frames_override=1,
            popen_factory=_NullStdinPopen,
            which=lambda _b: "ffmpeg",
        )

    class _RaisingCloseStdin:
        def write(self, _b: bytes) -> int:
            raise BrokenPipeError("broken")

        def close(self) -> None:
            raise OSError("close failed on broken pipe")

    class _RaisingClosePopen:
        def __init__(self, _cmd: List[str], **_kw: Any) -> None:
            self.stdin = _RaisingCloseStdin()

        def wait(self, timeout: float | None = None) -> int:
            return 1

    with pytest.raises(RuntimeError, match="FFmpeg quad showcase encode failed"):
        generate_quad_showcase(
            output_dir=tmp_path / "q_close_err",
            duration_sec=0.1,
            fps=10,
            renderer=QuadShowcaseRenderer(font_loader=fast_loader),
            popen_factory=_RaisingClosePopen,
            which=lambda _b: "ffmpeg",
        )

    with pytest.raises(RuntimeError, match="FFmpeg encode failed"):
        generate_benchmind_hackathon_demo(
            output_dir=tmp_path / "bm_close_err",
            renderer=BenchMindHackathonRenderer(font_loader=fast_loader),
            total_frames_override=1,
            popen_factory=_RaisingClosePopen,
            which=lambda _b: "ffmpeg",
        )


def test_soundtrack_synth_boundary_sample_quantization_and_crest_clamp() -> None:
    # 0-sample rounding guard (line 32)
    with pytest.raises(ValueError, match="yields 0 samples"):
        synthesize_soundtrack_pcm(duration_sec=0.0001, bpm=120.0, sample_rate=100)

    # Empty scene mask boundary (line 65)
    r_empty_scene = synthesize_soundtrack_pcm(duration_sec=5.0001, bpm=120.0, sample_rate=10)
    assert r_empty_scene["interleaved_pcm"].shape == (50, 2)

    # Beat sample boundary start_samp >= end_samp (line 105)
    r_beat_edge = synthesize_soundtrack_pcm(duration_sec=1.49, bpm=60.0 / 0.35, sample_rate=1)
    assert r_beat_edge["interleaved_pcm"].shape == (1, 2)

    # Text entrance boundary start_samp >= end_samp (line 121)
    r_tick_edge = synthesize_soundtrack_pcm(duration_sec=0.201, bpm=60.0, sample_rate=5)
    assert r_tick_edge["interleaved_pcm"].shape == (1, 2)

    # Scene cut whoosh boundary w_start >= w_end (line 135)
    r_whoosh_edge = synthesize_soundtrack_pcm(duration_sec=4.56, bpm=60.0, sample_rate=2)
    assert r_whoosh_edge["interleaved_pcm"].shape == (9, 2)

    # High crest-factor peak clamp (line 193: gain * curr_peak > max_peak_allowed)
    r_crest = synthesize_soundtrack_pcm(duration_sec=120.0, bpm=10.0, sample_rate=500)
    assert r_crest["peak_dbfs"] <= -1.0
    assert r_crest["rms_dbfs"] < -15.5
