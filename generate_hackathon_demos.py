#!/usr/bin/env python3
"""Automated 24-second 1920x1080 30fps Widescreen Hackathon Pitch Video Generator.

Renders two dedicated 16:9 widescreen (1920x1080, 30fps, 24.0s) hackathon demo videos:
  1. outputs/benchmind-v02-hackathon-demo-1920x1080.mp4
     (Meta Global AI Developer Hackathon — Team ID 1429535549246922)
  2. outputs/redflag-loop-sea-codex-demo-1920x1080.mp4
     (Sea × OpenAI Codex Hackathon — Autonomous & Adaptive AI)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agy_codex_studio.hackathon_demos import (
    generate_benchmind_hackathon_demo,
    generate_both_hackathon_demos,
    generate_redflag_hackathon_demo,
)


def _print_summary(label: str, meta: dict[str, Any]) -> None:
    probe = meta["probe_verification"]
    print(f"=== {label} ===")
    print(f"MP4 Video     : {meta['output_video']}")
    print(f"JSON Metadata : {meta['companion_json']}")
    print(f"SRT Captions  : {meta['companion_srt']}")
    print(f"Contact Sheet : {meta['contact_sheet']}")
    print(
        f"Stream Probe  : {probe['width']}x{probe['height']} @ {probe['fps']}fps | "
        f"video={probe['video_codec']} | audio={probe['audio_codec']} | duration={probe['duration_sec']:.2f}s"
    )


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    benchmind_fn: Callable[..., dict[str, Any]] = generate_benchmind_hackathon_demo,
    redflag_fn: Callable[..., dict[str, Any]] = generate_redflag_hackathon_demo,
    both_fn: Callable[..., dict[str, dict[str, Any]]] = generate_both_hackathon_demos,
) -> int:
    parser = argparse.ArgumentParser(
        description="Generate 24.0s 1920x1080 30fps Widescreen Hackathon Demo Videos (BenchMind v0.2.0 & RedFlag-Loop)."
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs"),
        help="Output directory for MP4, JSON, SRT, and contact sheets.",
    )
    parser.add_argument(
        "--target",
        choices=["all", "benchmind", "redflag"],
        default="all",
        help="Which hackathon demo video(s) to render.",
    )
    args = parser.parse_args(argv)

    if args.target == "benchmind":
        bm = benchmind_fn(output_dir=args.out_dir)
        _print_summary("BenchMind v0.2.0 (Meta Global AI Hackathon)", bm)
    elif args.target == "redflag":
        rf = redflag_fn(output_dir=args.out_dir)
        _print_summary("RedFlag-Loop (Sea × OpenAI Codex Hackathon)", rf)
    else:
        res = both_fn(output_dir=args.out_dir)
        _print_summary("BenchMind v0.2.0 (Meta Global AI Hackathon)", res["benchmind"])
        _print_summary("RedFlag-Loop (Sea × OpenAI Codex Hackathon)", res["redflag_loop"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
