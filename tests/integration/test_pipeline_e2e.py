from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from typing import Any, List
import wave

from PIL import ImageFont
import pytest

from agy_codex_studio.caption_engine import build_caption_groups, export_captions
from agy_codex_studio.cli import run_cli
from agy_codex_studio.contracts import MediaProbeResult, TranscriptSegment, WordTimestamp
from agy_codex_studio.ghost_trimmer import detect_and_trim_words
from agy_codex_studio.hackathon_demos import generate_both_hackathon_demos
from agy_codex_studio.quad_showcase import QuadShowcaseRenderer, generate_quad_showcase
from agy_codex_studio.shorts_scorer import score_transcript_segments
from agy_codex_studio.soundtrack_synth import synthesize_showcase_soundtrack


ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_root_script(module_name: str, filename: str) -> Any:
    script_path = ROOT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeStdin(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.total_bytes = 0
        self.closed_flag = False

    def write(self, b: bytes | bytearray | memoryview) -> int:  # type: ignore[override]
        if self.closed_flag:
            raise ValueError("write on closed pipe")
        n = len(b)
        self.total_bytes += n
        return n

    def close(self) -> None:
        self.closed_flag = True
        super().close()


class _FakeFFmpegPopen:
    def __init__(self, cmd: List[str], returncode: int = 0) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stdin = _FakeStdin()
        out_mp4 = Path(cmd[-1])
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode


def test_full_asr_to_captions_shorts_and_soundtrack_pipeline(tmp_path: Path) -> None:
    raw_words = [
        WordTimestamp("STM32", 0.10, 0.45),
        WordTimestamp("captures", 0.48, 0.82),
        WordTimestamp("uh", 0.85, 1.02),
        WordTimestamp("STM32", 1.10, 1.45),
        WordTimestamp("captures", 1.48, 1.85),
        WordTimestamp("4000", 1.88, 2.20),
        WordTimestamp("Hz", 2.22, 2.50),
        WordTimestamp("EMG,", 2.52, 2.90),
        # 1.40s silence gap -> should be trimmed by detect_and_trim_words
        WordTimestamp("um", 4.30, 4.50),
        WordTimestamp("achieving", 4.55, 4.95),
        WordTimestamp("99.5%", 4.98, 5.35),
        WordTimestamp("UART", 5.38, 5.70),
        WordTimestamp("recovery", 5.72, 6.15),
        WordTimestamp("and", 6.18, 6.35),
        WordTimestamp("-25.5", 6.38, 6.75),
        WordTimestamp("dB", 6.78, 7.05),
        WordTimestamp("notch", 7.08, 7.45),
        WordTimestamp("attenuation.", 7.48, 8.10),
    ]

    trim_res = detect_and_trim_words(raw_words, max_pause_sec=0.55)
    remapped: List[WordTimestamp] = trim_res["remapped_words"]
    assert trim_res["removed_fillers"] >= 1
    assert any("retake" in c.reason for c in trim_res["cut_intervals"])
    assert trim_res["saved_seconds"] > 1.0

    # Monotonic remapped timeline guarantee
    for idx in range(len(remapped) - 1):
        assert remapped[idx].start < remapped[idx].end <= remapped[idx + 1].start + 1e-6

    groups = build_caption_groups(remapped, max_words=4, pause_break_sec=0.45)
    assert len(groups) >= 3
    exported = export_captions(groups, tmp_path / "captions")
    cap_json = json.loads(Path(exported["json"]).read_text(encoding="utf-8"))
    cap_srt = Path(exported["srt"]).read_text(encoding="utf-8")
    cap_vtt = Path(exported["vtt"]).read_text(encoding="utf-8")

    assert cap_json["meta"]["group_count"] == len(groups)
    assert len(cap_json["captions"]) == len(groups)
    assert cap_srt.count(" --> ") == len(groups)
    assert cap_vtt.startswith("WEBVTT\n\n")

    segments = [
        TranscriptSegment(id=g.id, text=g.text, start=g.start, end=g.end, words=g.words)
        for g in groups
    ]
    candidates = score_transcript_segments(
        segments,
        target_min_sec=2.0,
        target_max_sec=12.0,
    )
    assert len(candidates) >= 1
    assert candidates[0].score > 5.0

    dur = max(1.0, groups[-1].end + 0.5)
    wav_out = tmp_path / "trimmed_soundtrack.wav"
    manifest = synthesize_showcase_soundtrack(wav_out, duration_sec=dur, bpm=120.0)
    assert wav_out.exists()
    with wave.open(str(wav_out), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getframerate() == 48000
        assert wf.getnframes() == int(round(dur * 48000))
    assert manifest.peak_dbfs <= -0.9


def test_quad_and_widescreen_hackathon_generators_end_to_end_with_stub_ffmpeg(tmp_path: Path) -> None:
    spawned: List[_FakeFFmpegPopen] = []
    fast_font_loader = lambda _cands, _sz: ImageFont.load_default()

    def popen_factory(cmd: List[str], **_kwargs: Any) -> _FakeFFmpegPopen:
        proc = _FakeFFmpegPopen(cmd, returncode=0)
        spawned.append(proc)
        return proc

    def fake_sheet(video_path: Path, out_png: Path, cols: int = 4, rows: int = 2) -> Path:
        assert Path(video_path).exists()
        out_png.write_bytes(b"\x89PNG\r\n\x1a\n")
        return out_png

    def fake_quad_probe(video_path: Path) -> MediaProbeResult:
        return MediaProbeResult(
            file=str(video_path),
            duration_sec=0.4,
            width=1080,
            height=1920,
            fps=10.0,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            file_size_bytes=Path(video_path).stat().st_size,
        )

    quad_meta = generate_quad_showcase(
        output_dir=tmp_path / "quad",
        duration_sec=0.4,
        fps=10,
        renderer=QuadShowcaseRenderer(font_loader=fast_font_loader),
        popen_factory=popen_factory,
        which=lambda _b: "ffmpeg",
        contact_sheet_fn=fake_sheet,
        probe_fn=fake_quad_probe,
    )
    assert len(spawned) == 1
    assert spawned[0].stdin.total_bytes == 4 * 1080 * 1920 * 3
    assert Path(quad_meta["output_video"]).exists()
    assert Path(quad_meta["companion_json"]).exists()
    assert Path(quad_meta["companion_srt"]).exists()
    assert Path(quad_meta["contact_sheet"]).exists()

    def fake_wide_probe(video_path: Path) -> MediaProbeResult:
        return MediaProbeResult(
            file=str(video_path),
            duration_sec=0.2,
            width=1920,
            height=1080,
            fps=30.0,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            file_size_bytes=Path(video_path).stat().st_size,
        )

    both = generate_both_hackathon_demos(
        output_dir=tmp_path / "wide",
        total_frames_override=3,
        popen_factory=popen_factory,
        which=lambda _b: "ffmpeg",
        contact_sheet_fn=fake_sheet,
        probe_fn=fake_wide_probe,
    )
    assert set(both.keys()) == {"benchmind", "redflag_loop"}
    assert len(spawned) == 3
    assert spawned[1].stdin.total_bytes == 3 * 1920 * 1080 * 3
    assert spawned[2].stdin.total_bytes == 3 * 1920 * 1080 * 3
    assert Path(both["benchmind"]["companion_json"]).exists()
    assert Path(both["redflag_loop"]["companion_json"]).exists()


def test_cli_subcommands_and_top_level_scripts_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assets_dir = tmp_path / "showcase_assets"
    rc = run_cli(["generate-showcase-assets", "--out-dir", str(assets_dir), "--duration", "4.0"])
    assert rc == 0
    cli_stdout = capsys.readouterr().out
    assert "Studio Manifest: studio_manifest.json" in cli_stdout
    manifest_json = json.loads((assets_dir / "studio_manifest.json").read_text(encoding="utf-8"))
    assert Path(manifest_json["soundtrack"]["file"]).exists()
    assert Path(manifest_json["captions"]["paths"]["srt"]).exists()
    assert len(manifest_json["short_segment_candidates"]) >= 1

    quad_mod = _load_root_script("gen_quad_root", "generate_quad_showcase.py")
    hack_mod = _load_root_script("gen_hack_root", "generate_hackathon_demos.py")

    sample_meta = {
        "output_video": str(tmp_path / "sample.mp4"),
        "companion_json": str(tmp_path / "sample.json"),
        "companion_srt": str(tmp_path / "sample.srt"),
        "contact_sheet": str(tmp_path / "sample.png"),
        "probe_verification": {
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "video_codec": "h264",
            "audio_codec": "aac",
            "duration_sec": 24.0,
        },
    }

    assert quad_mod.main(["--out-dir", str(tmp_path)], generator_fn=lambda output_dir: sample_meta) == 0
    assert "Quad Engineering Showcase Generated" in capsys.readouterr().out

    for target in ("benchmind", "redflag", "all"):
        rc_h = hack_mod.main(
            ["--out-dir", str(tmp_path), "--target", target],
            benchmind_fn=lambda output_dir: sample_meta,
            redflag_fn=lambda output_dir: sample_meta,
            both_fn=lambda output_dir: {"benchmind": sample_meta, "redflag_loop": sample_meta},
        )
        assert rc_h == 0
        out_h = capsys.readouterr().out
        assert "Stream Probe" in out_h
