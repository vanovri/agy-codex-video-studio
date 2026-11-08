from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .caption_engine import build_caption_groups, export_captions
from .contracts import TranscriptSegment, WordTimestamp
from .ffmpeg_bridge import (
    DEFAULT_SCRIPTS_DIR,
    extract_contact_sheet,
    probe_media,
    run_ffmpeg_skill,
)
from .quad_showcase import generate_quad_showcase
from .shorts_scorer import score_transcript_segments
from .soundtrack_synth import synthesize_showcase_soundtrack


def _get_showcase_transcript_words() -> List[WordTimestamp]:
    """Pre-timed words corresponding strictly to the 10 showcase shots in studio/SPEC.md."""
    groups_def = [
        (0.2, 2.2, "50 Hz mains hum corrupts"),
        (2.4, 4.9, "raw surface EMG signals"),
        (5.1, 8.2, "STM32 captures 4,000 Hz via DMA"),
        (8.5, 11.8, "8,000 samples lock DC baseline"),
        (12.1, 15.7, "cascaded Butterworth biquad"),
        (16.0, 19.8, "carves a -25.5 dB notch canyon"),
        (20.1, 24.1, "grip RMS climbs to 52.71 mV"),
        (24.4, 28.5, "Pearson r = 0.9941 linearity"),
        (29.1, 32.3, "12,043 rows zero drops"),
        (32.6, 35.9, "SignalProof Lab x ENVIID MRV"),
    ]

    all_words: List[WordTimestamp] = []
    for g_start, g_end, text in groups_def:
        tokens = text.split()
        dur = max(0.1, g_end - g_start)
        word_dur = dur / len(tokens)
        for i, token in enumerate(tokens):
            w_s = round(g_start + i * word_dur, 3)
            w_e = round(g_end, 3) if i == len(tokens) - 1 else round(w_s + word_dur * 0.88, 3)
            all_words.append(WordTimestamp(word=token, start=w_s, end=w_e, score=0.99))
    return all_words


def _default_whisper_checker() -> str:
    import faster_whisper

    return str(getattr(faster_whisper, "__version__", "installed"))


def _first_line(stdout: Optional[str]) -> str:
    if not stdout:
        return ""
    lines = stdout.splitlines()
    return lines[0].strip() if lines else ""


def inspect_environment(
    *,
    which: Callable[[str], Optional[str]] = shutil.which,
    runner: Callable[..., Any] = subprocess.run,
    skill_runner: Callable[[str, List[str]], Dict[str, Any]] = run_ffmpeg_skill,
    whisper_checker: Callable[[], str] = _default_whisper_checker,
) -> Dict[str, Any]:
    """Pure environment health inspector with injectable system boundaries."""
    report: Dict[str, Any] = {
        "ffmpeg": None,
        "ffprobe": None,
        "yt_dlp": None,
        "faster_whisper": None,
        "hyperframes": None,
        "ffmpeg_skill": None,
        "all_ok": True,
    }

    # 1. ffmpeg
    ff_bin = which("ffmpeg")
    if ff_bin:
        try:
            p = runner([ff_bin, "-version"], capture_output=True, text=True, check=True)
            report["ffmpeg"] = {"status": "ok", "path": ff_bin, "version": _first_line(p.stdout)}
        except Exception as e:
            report["ffmpeg"] = {"status": "error", "error": str(e)}
            report["all_ok"] = False
    else:
        report["ffmpeg"] = {"status": "missing"}
        report["all_ok"] = False

    # 2. ffprobe
    probe_bin = which("ffprobe")
    if probe_bin:
        try:
            p = runner([probe_bin, "-version"], capture_output=True, text=True, check=True)
            report["ffprobe"] = {"status": "ok", "path": probe_bin, "version": _first_line(p.stdout)}
        except Exception as e:
            report["ffprobe"] = {"status": "error", "error": str(e)}
            report["all_ok"] = False
    else:
        report["ffprobe"] = {"status": "missing"}
        report["all_ok"] = False

    # 3. yt-dlp
    ytdlp_bin = which("yt-dlp")
    if ytdlp_bin:
        try:
            p = runner([ytdlp_bin, "--version"], capture_output=True, text=True, check=True)
            report["yt_dlp"] = {"status": "ok", "path": ytdlp_bin, "version": (p.stdout or "").strip()}
        except Exception as e:
            report["yt_dlp"] = {"status": "error", "error": str(e)}
    else:
        report["yt_dlp"] = {"status": "missing"}

    # 4. faster_whisper
    try:
        ver = whisper_checker()
        report["faster_whisper"] = {"status": "ok", "version": ver}
    except Exception as e:
        report["faster_whisper"] = {"status": "missing", "error": str(e)}

    # 5. hyperframes (strictly shell=False + exit-code verification)
    hf_direct = which("hyperframes")
    npx_bin = None if hf_direct else (which("npx.cmd") or which("npx"))
    if hf_direct or npx_bin:
        try:
            cmd = [hf_direct, "--version"] if hf_direct else [str(npx_bin), "hyperframes", "--version"]
            p = runner(cmd, capture_output=True, text=True, shell=False)
            if p.returncode == 0:
                report["hyperframes"] = {"status": "ok", "version": (p.stdout or "").strip()}
            else:
                err_msg = (p.stderr or p.stdout or f"exit code {p.returncode}").strip()
                report["hyperframes"] = {"status": "error", "error": err_msg}
        except Exception as e:
            report["hyperframes"] = {"status": "error", "error": str(e)}
    else:
        report["hyperframes"] = {"status": "missing"}

    # 6. ffmpeg-skill contract
    try:
        skill_doc = skill_runner("_contract", ["doctor"])
        report["ffmpeg_skill"] = {
            "status": "ok",
            "repo": str(DEFAULT_SCRIPTS_DIR),
            "version": skill_doc.get("version"),
            "ok": skill_doc.get("ok"),
        }
    except Exception as e:
        report["ffmpeg_skill"] = {"status": "error", "error": str(e)}
        report["all_ok"] = False

    return report


def cmd_doctor(
    args: argparse.Namespace,
    *,
    which: Callable[[str], Optional[str]] = shutil.which,
    runner: Callable[..., Any] = subprocess.run,
    skill_runner: Callable[[str, List[str]], Dict[str, Any]] = run_ffmpeg_skill,
    whisper_checker: Callable[[], str] = _default_whisper_checker,
) -> int:
    """Check availability of ffmpeg, ffprobe, yt-dlp, faster_whisper, hyperframes, and ffmpeg-skill."""
    report = inspect_environment(
        which=which,
        runner=runner,
        skill_runner=skill_runner,
        whisper_checker=whisper_checker,
    )

    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        print("=== AGY x Codex Video Studio: Doctor Inspection ===")
        for tool, info in report.items():
            if tool == "all_ok":
                continue
            status = info.get("status") if isinstance(info, dict) else info
            ver = info.get("version", "") if isinstance(info, dict) else ""
            print(f"[{str(status).upper()}] {tool:16s} : {ver}")
        print(f"Overall status: {'HEALTHY' if report['all_ok'] else 'DEGRADED'}")

    return 0 if report["all_ok"] else 1


def cmd_generate_showcase_assets(args: argparse.Namespace) -> int:
    """Generate soundtrack.wav, captions (json, srt, vtt), and studio_manifest.json."""
    duration = float(args.duration)
    if not math.isfinite(duration) or duration <= 0.0:
        raise ValueError(f"duration must be a finite number > 0, got {args.duration!r}")

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Synthesizing 48kHz stereo showcase soundtrack ({duration:.1f}s)...")
    wav_path = out_dir / "soundtrack.wav"
    soundtrack_manifest = synthesize_showcase_soundtrack(wav_path, duration_sec=duration, bpm=120.0)

    print("[2/3] Generating word-level captions and timed groups...")
    raw_words = _get_showcase_transcript_words()
    caption_groups = build_caption_groups(raw_words, max_words=7, pause_break_sec=0.18)
    caption_paths = export_captions(caption_groups, out_dir)

    print("[3/3] Scoring candidate shorts and building studio manifest...")
    segments: List[TranscriptSegment] = [
        TranscriptSegment(
            id=g.id,
            text=g.text,
            start=g.start,
            end=g.end,
            words=g.words,
        )
        for g in caption_groups
    ]
    candidates = score_transcript_segments(segments, target_min_sec=15.0, target_max_sec=45.0)

    verified_metrics = {
        "adc_rate_hz": 4000,
        "hum_attenuation_db": -25.5,
        "notch_q": 30.0,
        "calibration_samples": 8000,
        "calibration_time_sec": 2.0,
        "rms_window_samples": 400,
        "rms_window_ms": 100,
        "grip_rms_levels_mv": {
            "relax": 7.64,
            "light": 16.10,
            "medium": 38.52,
            "strong": 52.71,
        },
        "pearson_r": 0.9941,
        "telemetry_rows": 12043,
        "dropped_packets": 0,
        "verification_hashes": ["CRC-32", "SHA-256"],
        "project_pairing": "SignalProof Lab (STM32) x ENVIID Corn Cob Biochar Digital MRV",
    }

    manifest = {
        "title": "SignalProof Lab x ENVIID Deterministic Engineering Reel",
        "author": "Ardhya Novri Ramadhan",
        "output_spec": {
            "resolution": [1080, 1920],
            "fps": 30,
            "duration_sec": duration,
            "bpm": 120.0,
            "safe_zone": {"x": [90, 990], "y": [172, 1320], "captions_y": [1185, 1315]},
        },
        "soundtrack": soundtrack_manifest.to_dict(),
        "captions": {
            "paths": caption_paths,
            "count": len(caption_groups),
            "groups": [g.to_dict() for g in caption_groups],
        },
        "short_segment_candidates": [c.to_dict() for c in candidates[:5]],
        "verified_metrics": verified_metrics,
    }

    manifest_file = out_dir / "studio_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Showcase assets successfully created in: {out_dir}")
    print(
        f" - Soundtrack: {wav_path.name} "
        f"(Peak: {soundtrack_manifest.peak_dbfs:.2f} dBFS, RMS: {soundtrack_manifest.rms_dbfs:.2f} dBFS)"
    )
    print(
        f" - Captions: {Path(caption_paths['json']).name}, "
        f"{Path(caption_paths['srt']).name}, {Path(caption_paths['vtt']).name}"
    )
    print(f" - Studio Manifest: {manifest_file.name}")
    return 0


def cmd_verify_render(
    args: argparse.Namespace,
    *,
    probe_fn: Callable[..., Any] = probe_media,
    skill_runner: Callable[[str, List[str]], Dict[str, Any]] = run_ffmpeg_skill,
    contact_sheet_fn: Callable[..., Path] = extract_contact_sheet,
) -> int:
    """Verify rendered video against platform spec, probe properties, and extract contact sheet."""
    expected_duration = float(args.expected_duration)
    if not math.isfinite(expected_duration) or expected_duration <= 0.0:
        raise ValueError(
            f"expected_duration must be a finite number > 0, got {args.expected_duration!r}"
        )

    mp4_path = Path(args.mp4_path).resolve()
    if not mp4_path.exists():
        print(f"Error: Rendered file not found: {mp4_path}")
        return 1

    out_dir = Path(args.out_dir).resolve() if getattr(args, "out_dir", "") else mp4_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Probing rendered video {mp4_path.name}...")
    probe_result = probe_fn(mp4_path)

    print("Running compliance check with ffmpeg-skill check.py...")
    compliance_check: Dict[str, Any] = {}
    try:
        compliance_check = skill_runner("check", [str(mp4_path), "--platform", "reels"])
    except Exception as e:
        compliance_check = {"status": "error", "error": str(e)}

    print("Extracting 4x3 contact sheet...")
    sheet_png = out_dir / f"{mp4_path.stem}_sheet.png"
    contact_sheet_fn(mp4_path, sheet_png, cols=4, rows=3)

    dur_diff = abs(probe_result.duration_sec - expected_duration)
    is_duration_ok = dur_diff <= 0.5
    is_resolution_ok = probe_result.width == 1080 and probe_result.height == 1920

    verification_data = {
        "file": str(mp4_path),
        "expected_duration": expected_duration,
        "measured_duration": probe_result.duration_sec,
        "duration_difference": round(dur_diff, 3),
        "duration_ok": is_duration_ok,
        "resolution": [probe_result.width, probe_result.height],
        "resolution_ok": is_resolution_ok,
        "fps": probe_result.fps,
        "video_codec": probe_result.video_codec,
        "audio_codec": probe_result.audio_codec,
        "contact_sheet": str(sheet_png) if sheet_png.exists() else None,
        "compliance_check": compliance_check,
    }

    out_json = out_dir / "render_verification.json"
    out_json.write_text(json.dumps(verification_data, indent=2), encoding="utf-8")

    print(f"Verification completed. Output written to: {out_json}")
    print(
        f"Duration: {probe_result.duration_sec:.2f}s (OK: {is_duration_ok}), "
        f"Resolution: {probe_result.width}x{probe_result.height} (OK: {is_resolution_ok})"
    )
    is_compliance_ok = isinstance(compliance_check, dict) and (compliance_check.get("ok") is True)
    return 0 if (is_duration_ok and is_resolution_ok and is_compliance_ok) else 1


def cmd_generate_quad_showcase(
    args: argparse.Namespace,
    *,
    generator_fn: Callable[..., Dict[str, Any]] = generate_quad_showcase,
) -> int:
    """Synthesize the 24s 1080x1920 30fps Quad Engineering Showcase reel + JSON & SRT metadata."""
    out_dir = Path(args.out_dir).resolve()
    metadata = generator_fn(output_dir=out_dir)
    probe = metadata["probe_verification"]
    companion_json = metadata.get("companion_json") or metadata["output_video"].replace(
        "-1080x1920.mp4", ".json"
    )
    print(f"Quad Showcase rendered to: {metadata['output_video']}")
    print(f"Companion JSON: {companion_json}")
    print(f"Companion SRT : {metadata['companion_srt']}")
    print(
        f"Verified Stream: {probe['width']}x{probe['height']} @ {probe['fps']}fps | "
        f"video={probe['video_codec']} | audio={probe['audio_codec']} | duration={probe['duration_sec']:.2f}s"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agy-codex-studio",
        description="AGY x Codex Video Studio backend pipeline and asset generator.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_doctor = subparsers.add_parser("doctor", help="Inspect required environment tools.")
    p_doctor.add_argument("--json", action="store_true", help="Output doctor result as JSON.")
    p_doctor.set_defaults(func=cmd_doctor)

    p_gen = subparsers.add_parser(
        "generate-showcase-assets", help="Generate soundtrack, captions, and manifest."
    )
    p_gen.add_argument(
        "--out-dir",
        default=str(Path(r"C:\Users\ardhy\Projects\agy-codex-video-studio\studio\assets")),
        help="Directory to save generated assets.",
    )
    p_gen.add_argument(
        "--duration",
        type=float,
        default=36.0,
        help="Soundtrack and reel duration in seconds.",
    )
    p_gen.set_defaults(func=cmd_generate_showcase_assets)

    p_verify = subparsers.add_parser("verify-render", help="Verify rendered MP4 video.")
    p_verify.add_argument("mp4_path", help="Path to rendered MP4 video.")
    p_verify.add_argument(
        "--expected-duration",
        type=float,
        default=36.0,
        help="Target duration in seconds.",
    )
    p_verify.add_argument(
        "--out-dir",
        default="",
        help="Directory to store contact sheet and verification JSON.",
    )
    p_verify.set_defaults(func=cmd_verify_render)

    p_quad = subparsers.add_parser(
        "generate-quad-showcase",
        help="Synthesize 24s 1080x1920 30fps 4-system engineering reel + JSON/SRT metadata.",
    )
    p_quad.add_argument(
        "--out-dir",
        default=str(Path(r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs")),
        help="Directory to store output MP4, JSON, SRT, and contact sheet.",
    )
    p_quad.set_defaults(func=cmd_generate_quad_showcase)

    return parser


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(argv)
    return int(parsed.func(parsed))


def main() -> None:
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
