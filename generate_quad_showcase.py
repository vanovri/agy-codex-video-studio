#!/usr/bin/env python3
"""Automated 24-second 1080x1920 30fps Multi-Project Engineering Showcase Generator.

Highlights Ardhya Novri Ramadhan's 4 flagship engineering systems:
  1. Scene 1 (0-6s)  : STM32F411 EMG Digital Filter Pipeline (4,000 Hz ADC+DMA, Butterworth 20-500 Hz + 50 Hz Notch Q=30, 100 ms RMS/MAV, r=0.994)
  2. Scene 2 (6-12s) : UART Fixture Kit (v0.1.0) (130 pytest pass, 15/15 synthetic stream fixtures, CRC-32 & framing stress verification)
  3. Scene 3 (12-18s): BenchMind (v0.2.0) (Meta Global AI Hackathon - 1,997/1,997 UART frames recovered, 25.5 dB 50 Hz hum attenuation, AI root-cause copilot)
  4. Scene 4 (18-24s): Packing Arena (v0.1.0) & Portfolio (ardhyanovri.my.id) (Interactive 2D bin-packing heuristics & full-stack engineering showcase)
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

from agy_codex_studio.quad_showcase import generate_quad_showcase


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    generator_fn: Callable[..., dict[str, Any]] = generate_quad_showcase,
) -> int:
    parser = argparse.ArgumentParser(description="Generate Ardhya's 24s 1080x1920 30fps Quad Engineering Showcase reel.")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs"),
        help="Output directory for MP4, JSON, SRT, and contact sheet.",
    )
    args = parser.parse_args(argv)

    metadata = generator_fn(output_dir=args.out_dir)
    probe = metadata["probe_verification"]
    json_meta = metadata.get("companion_json") or str(Path(args.out_dir) / "ardhya-engineering-quad-showcase.json")
    print("=== Quad Engineering Showcase Generated ===")
    print(f"MP4 Video     : {metadata['output_video']}")
    print(f"JSON Metadata : {json_meta}")
    print(f"SRT Captions  : {metadata['companion_srt']}")
    print(f"Contact Sheet : {metadata['contact_sheet']}")
    print(
        f"Stream Probe  : {probe['width']}x{probe['height']} @ {probe['fps']}fps | "
        f"video={probe['video_codec']} | audio={probe['audio_codec']} | duration={probe['duration_sec']:.2f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
