from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .caption_engine import _format_srt_time, build_caption_groups
from .contracts import CaptionGroup, WordTimestamp
from .ffmpeg_bridge import extract_contact_sheet, probe_media
from .soundtrack_synth import synthesize_showcase_soundtrack


QUAD_SCENES_SPEC: List[Dict[str, Any]] = [
    {
        "scene_id": "scene_01_stm32_emg",
        "index": 1,
        "start_sec": 0.0,
        "end_sec": 6.0,
        "eyebrow": "SCENE 01 / 04 · EMBEDDED DSP & BIOMEDICAL TELEMETRY",
        "title": "STM32F411 EMG FILTER PIPELINE",
        "subtitle": "Nominal 4,000 Hz 12-Bit ADC + DMA · Cascaded Biquad IIR",
        "metrics": [
            {"label": "SAMPLING RATE", "value": "4,000 Hz", "detail": "12-bit ADC1 PA0 + Circular DMA"},
            {"label": "BIQUAD CASCADE", "value": "20-500 Hz", "detail": "2nd-Order Butterworth + 50 Hz Notch Q=30"},
            {"label": "FEATURE WINDOW", "value": "100 ms", "detail": "400-Sample RMS/MAV · Pearson r = 0.994"},
        ],
        "caption_segments": [
            (0.15, 2.95, "STM32F411 captures 4,000 Hz EMG via DMA"),
            (3.05, 5.85, "Butterworth 20-500 Hz + Q=30 Notch locks r=0.994"),
        ],
    },
    {
        "scene_id": "scene_02_uart_fixture_kit",
        "index": 2,
        "start_sec": 6.0,
        "end_sec": 12.0,
        "eyebrow": "SCENE 02 / 04 · SERIAL PROTOCOL VERIFICATION SUITE",
        "title": "UART FIXTURE KIT v0.1.0",
        "subtitle": "Deterministic Byte-Stream Framing & Fault Injection",
        "metrics": [
            {"label": "TEST SUITE", "value": "130 PASS", "detail": "100% Deterministic Pytest Verification"},
            {"label": "STREAM FIXTURES", "value": "15 / 15", "detail": "Fragmented Chunks, Noise & Baud Jitter"},
            {"label": "INTEGRITY GUARD", "value": "CRC-32", "detail": "Framing Stress & Multi-OS CI Matrix"},
        ],
        "caption_segments": [
            (6.15, 8.95, "UART Fixture Kit v0.1.0: 130 pytest pass"),
            (9.05, 11.85, "15/15 synthetic stream fixtures & CRC-32 stress"),
        ],
    },
    {
        "scene_id": "scene_03_benchmind",
        "index": 3,
        "start_sec": 12.0,
        "end_sec": 18.0,
        "eyebrow": "SCENE 03 / 04 · META GLOBAL AI HACKATHON",
        "title": "BENCHMIND v0.2.0",
        "subtitle": "AI Root-Cause Hardware Copilot & Signal Recovery",
        "metrics": [
            {"label": "FRAME RECOVERY", "value": "1,997 / 1,997", "detail": "100% Valid UART Telemetry Frames Recovered"},
            {"label": "HUM ATTENUATION", "value": "-25.5 dB", "detail": "50 Hz Mains Interference Suppression"},
            {"label": "DIAGNOSTIC ENGINE", "value": "AI COPILOT", "detail": "Automated Hardware Fault Isolation Ledger"},
        ],
        "caption_segments": [
            (12.15, 14.95, "BenchMind v0.2.0 recovers 1,997/1,997 UART frames"),
            (15.05, 17.85, "25.5 dB 50 Hz hum suppression & AI root-cause copilot"),
        ],
    },
    {
        "scene_id": "scene_04_packing_arena_portfolio",
        "index": 4,
        "start_sec": 18.0,
        "end_sec": 24.0,
        "eyebrow": "SCENE 04 / 04 · ALGORITHMS & FULL-STACK ENGINEERING",
        "title": "PACKING ARENA & PORTFOLIO",
        "subtitle": "Interactive 2D Bin-Packing Heuristics · ardhyanovri.my.id",
        "metrics": [
            {"label": "PACKING ARENA", "value": "v0.1.0 LIVE", "detail": "Real-Time 2D Bin-Packing Heuristics Arena"},
            {"label": "SIGNAL LAB", "value": "60 FPS 3D", "detail": "Interactive WebGL Waterfall & Biquad Workbench"},
            {"label": "PORTFOLIO HUB", "value": "ardhyanovri.my.id", "detail": "Verified Hardware, DSP, Python & Web Systems"},
        ],
        "caption_segments": [
            (18.15, 20.95, "Packing Arena v0.1.0 interactive 2D bin-packing"),
            (21.05, 23.85, "Explore full-stack proofs at ardhyanovri.my.id"),
        ],
    },
]


def get_quad_showcase_words() -> List[WordTimestamp]:
    """Return word-level timestamps across the 4 scenes (0-24s)."""
    all_words: List[WordTimestamp] = []
    for scene in QUAD_SCENES_SPEC:
        for seg_start, seg_end, text in scene["caption_segments"]:
            tokens = text.split()
            dur = max(0.1, seg_end - seg_start)
            word_dur = dur / len(tokens)
            for idx, token in enumerate(tokens):
                w_s = round(seg_start + idx * word_dur, 3)
                w_e = round(seg_end, 3) if idx == len(tokens) - 1 else round(w_s + word_dur * 0.9, 3)
                all_words.append(WordTimestamp(word=token, start=w_s, end=w_e, score=0.99))
    return all_words


def build_quad_caption_groups() -> List[CaptionGroup]:
    """Build deterministic caption groups matching the 8 half-scene segments."""
    groups: List[CaptionGroup] = []
    grp_idx = 1
    for scene in QUAD_SCENES_SPEC:
        for seg_start, seg_end, text in scene["caption_segments"]:
            tokens = text.split()
            dur = max(0.1, seg_end - seg_start)
            word_dur = dur / len(tokens)
            words: List[WordTimestamp] = []
            for idx, token in enumerate(tokens):
                w_s = round(seg_start + idx * word_dur, 3)
                w_e = round(seg_end, 3) if idx == len(tokens) - 1 else round(w_s + word_dur * 0.9, 3)
                words.append(WordTimestamp(word=token, start=w_s, end=w_e, score=0.99))
            groups.append(
                CaptionGroup(
                    id=f"quad_cg_{grp_idx:02d}",
                    text=text,
                    start=seg_start,
                    end=seg_end,
                    words=words,
                )
            )
            grp_idx += 1
    return groups


def _load_font(
    candidates: List[str],
    size: int,
    *,
    fonts_dir: Union[str, Path] = r"C:\Windows\Fonts",
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    base = Path(fonts_dir)
    for name in candidates:
        p = base / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


class QuadShowcaseRenderer:
    """High-contrast 1080x1920 30fps frame synthesizer for the 4-scene engineering reel."""

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30
    DURATION_SEC = 24.0
    TOTAL_FRAMES = 720

    # Palette (matches studio/SPEC.md Industrial Oscilloscope & Drafting Vellum)
    BG_DARK = (17, 21, 28)          # #11151C
    BG_PANEL = (25, 31, 42)         # #191F2A
    BG_VELLUM = (244, 241, 234)     # #F4F1EA
    INK_LIGHT = (244, 241, 234)     # #F4F1EA
    INK_MUTED = (148, 163, 184)     # #94A3B8
    INK_DARK = (17, 21, 28)         # #11151C
    ACCENT_ORANGE = (255, 77, 28)   # #FF4D1C
    ACCENT_GREEN = (16, 185, 129)   # #10B981
    ACCENT_CYAN = (56, 189, 248)    # #38BDF8
    ACCENT_AMBER = (245, 158, 11)   # #F59E0B
    GRID_COLOR = (34, 42, 56)

    def __init__(
        self,
        *,
        font_loader: Optional[Callable[[List[str], int], Any]] = None,
    ) -> None:
        loader = font_loader or _load_font
        self.font_eyebrow = loader(["consolab.ttf", "arialbd.ttf"], 25)
        self.font_title = loader(["bahnschrift.ttf", "segoeuib.ttf", "arialbd.ttf"], 54)
        self.font_subtitle = loader(["segoeuib.ttf", "arialbd.ttf"], 28)
        self.font_metric_val = loader(["consolab.ttf", "arialbd.ttf"], 42)
        self.font_metric_lbl = loader(["consolab.ttf", "arialbd.ttf"], 22)
        self.font_metric_sub = loader(["segoeui.ttf", "arial.ttf"], 23)
        self.font_mono_sm = loader(["consolab.ttf", "consola.ttf"], 22)
        self.font_mono_xs = loader(["consola.ttf", "arial.ttf"], 19)
        self.font_caption = loader(["segoeuib.ttf", "arialbd.ttf"], 32)
        self.font_footer = loader(["consolab.ttf", "arialbd.ttf"], 22)
        self.caption_groups = build_quad_caption_groups()

        # Pre-build background plate with 24px structural grid
        self.base_bg = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_DARK)
        draw = ImageDraw.Draw(self.base_bg)
        for x in range(0, self.WIDTH, 36):
            draw.line([(x, 0), (x, self.HEIGHT)], fill=self.GRID_COLOR, width=1)
        for y in range(0, self.HEIGHT, 36):
            draw.line([(0, y), (self.WIDTH, y)], fill=self.GRID_COLOR, width=1)

        # Structural safe-zone frame rails
        draw.rectangle([72, 148, 1008, 1772], outline=(45, 55, 72), width=2)

    @staticmethod
    def _ease_out_cubic(x: float) -> float:
        x = max(0.0, min(1.0, x))
        return 1.0 - (1.0 - x) ** 3

    def _draw_header(
        self,
        draw: ImageDraw.ImageDraw,
        scene: Dict[str, Any],
        local_t: float,
        global_t: float,
    ) -> None:
        enter = self._ease_out_cubic(local_t / 0.35)
        y_offset = int((1.0 - enter) * -18)

        # Top telemetry status bar (y: 172..224)
        draw.rectangle([90, 172, 990, 224], fill=self.BG_PANEL, outline=(56, 70, 92), width=2)
        draw.rectangle([90, 172, 104, 224], fill=self.ACCENT_ORANGE)
        draw.text((120, 184), scene["eyebrow"], font=self.font_eyebrow, fill=self.INK_LIGHT)

        # Global timecode pill on right
        tc_str = f"T+{global_t:05.2f}s"
        draw.text((845, 184), tc_str, font=self.font_eyebrow, fill=self.ACCENT_GREEN)

        # Scene Progress Segmented Bar (4 segments)
        seg_w = (990 - 90 - 30) // 4
        for i in range(4):
            sx0 = 90 + i * (seg_w + 10)
            sx1 = sx0 + seg_w
            sy0, sy1 = 236, 246
            draw.rectangle([sx0, sy0, sx1, sy1], fill=(38, 47, 62))
            if i + 1 < scene["index"]:
                draw.rectangle([sx0, sy0, sx1, sy1], fill=self.ACCENT_GREEN)
            elif i + 1 == scene["index"]:
                prog = max(0.0, min(1.0, local_t / 6.0))
                fill_w = int(seg_w * prog)
                draw.rectangle([sx0, sy0, sx0 + fill_w, sy1], fill=self.ACCENT_ORANGE)

        # Hero Title & Subtitle (y: 262..378)
        draw.text((90, 264 + y_offset), scene["title"], font=self.font_title, fill=self.INK_LIGHT)
        draw.text((90, 332 + y_offset), scene["subtitle"], font=self.font_subtitle, fill=self.INK_MUTED)

    def _draw_scene1_visual(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        # Visual Box: x=[90, 990], y=[385, 795]
        vx0, vy0, vx1, vy1 = 90, 385, 990, 795
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(64, 80, 105), width=2)

        # Oscilloscope grid lines
        for gx in range(vx0 + 60, vx1, 60):
            draw.line([(gx, vy0), (gx, vy1)], fill=(24, 32, 44), width=1)
        for gy in range(vy0 + 50, vy1, 50):
            draw.line([(vx0, gy), (vx1, gy)], fill=(24, 32, 44), width=1)

        mid_top = vy0 + 105
        mid_bot = vy0 + 295
        draw.line([(vx0, vy0 + 200), (vx1, vy0 + 200)], fill=(45, 58, 76), width=2)

        # Labels
        draw.rectangle([vx0 + 16, vy0 + 14, vx0 + 470, vy0 + 46], fill=(35, 20, 22))
        draw.text(
            (vx0 + 26, vy0 + 19),
            "CH1 RAW ADC1 PA0 (50 Hz HUM + DC DRIFT)",
            font=self.font_mono_xs,
            fill=self.ACCENT_ORANGE,
        )

        draw.rectangle([vx0 + 16, vy0 + 214, vx0 + 560, vy0 + 246], fill=(14, 38, 32))
        draw.text(
            (vx0 + 26, vy0 + 219),
            "CH2 CASCADED BIQUAD (20-500 Hz + 50 Hz NOTCH Q=30)",
            font=self.font_mono_xs,
            fill=self.ACCENT_GREEN,
        )

        # Generate waveform points
        n_pts = 180
        raw_pts: List[Tuple[int, int]] = []
        filt_pts: List[Tuple[int, int]] = []
        phase = local_t * 5.0
        for i in range(n_pts):
            px = vx0 + 20 + int((vx1 - vx0 - 40) * (i / (n_pts - 1)))
            u = i / n_pts
            # Muscle burst envelope
            burst = math.exp(-((u - 0.32) / 0.11) ** 2) + 0.85 * math.exp(-((u - 0.72) / 0.13) ** 2)
            emg_carrier = (
                math.sin(2.0 * math.pi * 21.0 * u + phase * 2.2)
                + 0.6 * math.sin(2.0 * math.pi * 37.0 * u - phase * 1.7)
                + 0.4 * math.cos(2.0 * math.pi * 53.0 * u + phase * 3.1)
            )
            clean_sig = burst * emg_carrier * 34.0
            hum_50hz = 28.0 * math.sin(2.0 * math.pi * 8.0 * u + phase * 1.5)
            dc_drift = 14.0 * math.sin(2.0 * math.pi * 1.2 * u + local_t)
            raw_y = int(mid_top - (clean_sig * 0.7 + hum_50hz + dc_drift))
            filt_y = int(mid_bot - clean_sig * 1.15)
            raw_pts.append((px, max(vy0 + 52, min(vy0 + 192, raw_y))))
            filt_pts.append((px, max(vy0 + 252, min(vy1 - 16, filt_y))))

        draw.line(raw_pts, fill=self.ACCENT_ORANGE, width=3)
        draw.line(filt_pts, fill=self.ACCENT_GREEN, width=3)

        # Grip RMS progression bar strip at bottom of visual box
        grips = [("RELAX", "7.64 mV"), ("LIGHT", "16.10 mV"), ("MED RPE-5", "38.52 mV"), ("STRONG", "52.71 mV")]
        active_grip = min(3, int(local_t / 1.45))
        gw = (vx1 - vx0 - 50) // 4
        for idx, (g_name, g_val) in enumerate(grips):
            gx0 = vx0 + 16 + idx * (gw + 6)
            gy0 = vy1 - 54
            is_act = idx == active_grip
            bg_c = (22, 65, 50) if is_act else (24, 31, 42)
            bd_c = self.ACCENT_GREEN if is_act else (52, 65, 84)
            draw.rectangle([gx0, gy0, gx0 + gw, vy1 - 10], fill=bg_c, outline=bd_c, width=2)
            draw.text((gx0 + 10, gy0 + 10), f"{g_name}: {g_val}", font=self.font_mono_xs, fill=self.INK_LIGHT)

    def _draw_scene2_visual(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        # Visual Box: UART Fixture Kit stream & 15/15 fixture matrix
        vx0, vy0, vx1, vy1 = 90, 385, 990, 795
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(14, 18, 26), outline=(64, 80, 105), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "SYNTHETIC UART BYTE STREAM -> DETERMINISTIC FRAME PARSER",
            font=self.font_mono_sm,
            fill=self.ACCENT_CYAN,
        )

        # Animated incoming fragmented byte chunks
        chunks = [
            ("CHUNK #01 [FRAG]", "AA 55 01 90 0F A2 ...", "BUFFERED", self.ACCENT_AMBER),
            ("CHUNK #02 [JOIN]", "... 3C 7B CRC32:9F4A120E \\n", "FRAME OK", self.ACCENT_GREEN),
            ("CHUNK #03 [NOISE]", "FF 00 [BAD_CRC:E10944B2] \\n", "REJECTED", self.ACCENT_ORANGE),
            ("CHUNK #04 [BURST]", "AA 55 02 90 10 B4 CRC32:44D18A2C \\n", "FRAME OK", self.ACCENT_GREEN),
        ]
        visible_chunks = min(4, int(local_t / 1.1) + 1)
        for idx in range(visible_chunks):
            c_tag, c_hex, c_status, c_col = chunks[idx]
            cy0 = vy0 + 56 + idx * 54
            draw.rectangle([vx0 + 20, cy0, vx1 - 20, cy0 + 44], fill=(22, 28, 39), outline=(45, 56, 74), width=1)
            draw.text((vx0 + 32, cy0 + 11), c_tag, font=self.font_mono_xs, fill=self.INK_MUTED)
            draw.text((vx0 + 245, cy0 + 11), c_hex, font=self.font_mono_xs, fill=self.INK_LIGHT)
            draw.rectangle([vx1 - 165, cy0 + 7, vx1 - 32, cy0 + 37], fill=(18, 24, 34), outline=c_col, width=2)
            draw.text((vx1 - 150, cy0 + 11), c_status, font=self.font_mono_xs, fill=c_col)

        # 15/15 Fixture Grid & Pytest Counter at bottom of box
        passed_tests = int(round(130 * self._ease_out_cubic(min(1.0, local_t / 2.2))))
        draw.rectangle([vx0 + 20, vy0 + 284, vx1 - 20, vy1 - 18], fill=(20, 32, 30), outline=self.ACCENT_GREEN, width=2)
        draw.text(
            (vx0 + 36, vy0 + 298),
            f"PYTEST VERIFICATION: {passed_tests:3d} / 130 PASSED  |  FIXTURES: 15 / 15 GREEN",
            font=self.font_mono_sm,
            fill=self.ACCENT_GREEN,
        )

        # 15 fixture indicator blocks
        active_fix = int(round(15 * self._ease_out_cubic(min(1.0, local_t / 2.0))))
        cell_w = (vx1 - vx0 - 72 - 14 * 8) // 15
        for f_i in range(15):
            fx0 = vx0 + 36 + f_i * (cell_w + 8)
            fy0 = vy0 + 340
            col = self.ACCENT_GREEN if f_i < active_fix else (42, 52, 68)
            draw.rectangle([fx0, fy0, fx0 + cell_w, fy0 + 28], fill=col)

    def _draw_scene3_visual(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        # Visual Box: BenchMind v0.2.0 50 Hz Notch Canyon & 1,997/1,997 UART Recovery
        vx0, vy0, vx1, vy1 = 90, 385, 990, 795
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(14, 18, 26), outline=(64, 80, 105), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "BENCHMIND AI COPILOT · BODE NOTCH CANYON & FRAME RECOVERY",
            font=self.font_mono_sm,
            fill=self.ACCENT_ORANGE,
        )

        # Left sub-panel: Bode Magnitude Curve with sharp -25.5 dB notch at 50 Hz
        bx0, by0, bx1, by1 = vx0 + 20, vy0 + 54, vx0 + 480, vy1 - 20
        draw.rectangle([bx0, by0, bx1, by1], fill=(10, 14, 20), outline=(45, 58, 76), width=1)
        draw.text((bx0 + 14, by0 + 10), "MAGNITUDE RESPONSE (dB)", font=self.font_mono_xs, fill=self.INK_MUTED)

        # Draw passband & 50Hz notch curve
        curve_pts: List[Tuple[int, int]] = []
        depth_anim = self._ease_out_cubic(min(1.0, local_t / 1.5))
        for i in range(120):
            u = i / 119.0
            px = bx0 + 16 + int((bx1 - bx0 - 32) * u)
            # HPF roll-on below u=0.15, LPF roll-off above u=0.82, sharp notch at u=0.36 (50 Hz)
            hpf_db = -24.0 * math.exp(-u / 0.07)
            lpf_db = -22.0 * math.exp(-(1.0 - u) / 0.09)
            notch_db = -25.5 * depth_anim * math.exp(-((u - 0.36) / 0.028) ** 2)
            total_db = hpf_db + lpf_db + notch_db
            py = by0 + 65 - int((total_db / 30.0) * 195.0)
            curve_pts.append((px, max(by0 + 48, min(by1 - 24, py))))

        draw.line(curve_pts, fill=self.ACCENT_GREEN, width=4)
        # Callout marker at notch tip (u=0.36)
        nx = bx0 + 16 + int((bx1 - bx0 - 32) * 0.36)
        ny = by0 + 65 + int((25.5 * depth_anim / 30.0) * 195.0)
        draw.ellipse([nx - 6, ny - 6, nx + 6, ny + 6], fill=self.ACCENT_ORANGE)
        draw.text((nx + 12, ny - 14), "-25.5 dB @ 50 Hz", font=self.font_mono_xs, fill=self.ACCENT_ORANGE)

        # Right sub-panel: AI Root-Cause Hardware Copilot log
        rx0, ry0, rx1, ry1 = vx0 + 500, vy0 + 54, vx1 - 20, vy1 - 20
        draw.rectangle([rx0, ry0, rx1, ry1], fill=(18, 24, 34), outline=(56, 70, 92), width=1)
        frames_rec = int(round(1997 * self._ease_out_cubic(min(1.0, local_t / 2.0))))
        draw.text((rx0 + 16, ry0 + 14), "ROOT-CAUSE TRACE LEDGER", font=self.font_mono_xs, fill=self.ACCENT_CYAN)
        lines = [
            (f"UART Recovered: {frames_rec:,}/1,997", self.ACCENT_GREEN),
            ("Unrecovered Drops: 0 frames", self.INK_LIGHT),
            ("50 Hz Hum Delta: -25.5 dB", self.ACCENT_ORANGE),
            ("Fault Root: Mains + Framing", self.INK_LIGHT),
            ("Evidence: VERIFIED JSON", self.ACCENT_GREEN),
            ("Team ID: 1429535549246922", self.INK_MUTED),
        ]
        for idx, (txt, col) in enumerate(lines):
            draw.text((rx0 + 16, ry0 + 54 + idx * 44), txt, font=self.font_mono_xs, fill=col)

    def _draw_scene4_visual(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        # Visual Box: Packing Arena 2D Bin-Packing + Portfolio Hub
        vx0, vy0, vx1, vy1 = 90, 385, 990, 795
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(14, 18, 26), outline=(64, 80, 105), width=2)

        # Left sub-panel: Animated 2D Bin-Packing Arena container
        bx0, by0, bx1, by1 = vx0 + 20, vy0 + 20, vx0 + 470, vy1 - 20
        draw.rectangle([bx0, by0, bx1, by1], fill=(10, 14, 20), outline=self.ACCENT_CYAN, width=2)
        draw.text((bx0 + 14, by0 + 10), "2D BIN-PACKING ARENA v0.1.0", font=self.font_mono_xs, fill=self.ACCENT_CYAN)

        # Deterministic rectangles packing into the bin
        rects = [
            (14, 44, 190, 110, self.ACCENT_ORANGE, "EMG-DSP"),
            (210, 44, 224, 95, self.ACCENT_GREEN, "UART-KIT"),
            (14, 160, 145, 115, self.ACCENT_CYAN, "BENCHMIND"),
            (165, 145, 155, 130, self.ACCENT_AMBER, "ENVIID-MRV"),
            (326, 145, 108, 130, (168, 85, 247), "3D-LAB"),
            (14, 281, 260, 72, self.ACCENT_GREEN, "PORTFOLIO-WEB"),
            (280, 281, 154, 72, self.ACCENT_ORANGE, "CRC32-VERIFIED"),
        ]
        n_show = min(len(rects), int(local_t / 0.55) + 2)
        for idx in range(n_show):
            rx, ry, rw, rh, rcol, rlabel = rects[idx]
            x0, y0 = bx0 + rx, by0 + ry
            draw.rectangle([x0, y0, x0 + rw, y0 + rh], fill=(24, 32, 46), outline=rcol, width=3)
            draw.text((x0 + 10, y0 + (rh // 2) - 10), rlabel, font=self.font_mono_xs, fill=self.INK_LIGHT)

        # Right sub-panel: Drafting Vellum Portfolio Verification Card
        px0, py0, px1, py1 = vx0 + 490, vy0 + 20, vx1 - 20, vy1 - 20
        draw.rectangle([px0, py0, px1, py1], fill=self.BG_VELLUM, outline=self.INK_DARK, width=3)
        draw.rectangle([px0, py0, px1, py0 + 48], fill=self.ACCENT_ORANGE)
        draw.text((px0 + 16, py0 + 12), "ENGINEERING PORTFOLIO LEDGER", font=self.font_mono_xs, fill=self.INK_LIGHT)

        vellum_lines = [
            ("ENGINEER:", "Ardhya Novri Ramadhan, S.T."),
            ("DEGREE:", "B.Eng. Electrical (UNDIP)"),
            ("LIVE WEB:", "ardhyanovri.my.id"),
            ("GITHUB:", "github.com/vanovri"),
            ("3D LAB:", "signal-lab.html (60fps)"),
            ("STATUS:", "4/4 SYSTEMS VERIFIED"),
        ]
        for idx, (k, v) in enumerate(vellum_lines):
            ly = py0 + 66 + idx * 48
            draw.text((px0 + 16, ly), k, font=self.font_mono_xs, fill=(71, 85, 105))
            draw.text((px0 + 132, ly), v, font=self.font_mono_xs, fill=self.INK_DARK)

    def _draw_metric_cards(
        self,
        draw: ImageDraw.ImageDraw,
        scene: Dict[str, Any],
        local_t: float,
    ) -> None:
        # 3 Horizontal Metric Cards inside y: [815, 1165], x: [90, 990]
        metrics = scene["metrics"]
        for idx, m in enumerate(metrics):
            delay = 0.15 + idx * 0.18
            prog = self._ease_out_cubic((local_t - delay) / 0.45)
            if prog <= 0.01:
                continue
            x_shift = int((1.0 - prog) * 32)
            cy0 = 815 + idx * 116
            cy1 = cy0 + 102
            cx0 = 90 + x_shift
            cx1 = 990

            # Card plate
            is_hero = idx == 0
            border_col = self.ACCENT_ORANGE if is_hero else self.ACCENT_GREEN
            draw.rectangle([cx0, cy0, cx1, cy1], fill=self.BG_PANEL, outline=border_col, width=2)
            draw.rectangle([cx0, cy0, cx0 + 12, cy1], fill=border_col)

            # Label + Detail on left, Hero Value on right
            draw.text((cx0 + 28, cy0 + 14), m["label"], font=self.font_metric_lbl, fill=self.INK_MUTED)
            draw.text((cx0 + 28, cy0 + 50), m["detail"], font=self.font_metric_sub, fill=self.INK_LIGHT)

            val_str = m["value"]
            val_col = self.ACCENT_ORANGE if is_hero else self.ACCENT_GREEN
            bbox = draw.textbbox((0, 0), val_str, font=self.font_metric_val)
            vw = bbox[2] - bbox[0]
            draw.text((cx1 - vw - 26, cy0 + 24), val_str, font=self.font_metric_val, fill=val_col)

    def _draw_captions_and_footer(self, draw: ImageDraw.ImageDraw, global_t: float) -> None:
        # Safe zone caption band: y: [1185, 1315], x: [90, 990]
        active_group: CaptionGroup | None = None
        for grp in self.caption_groups:
            if grp.start <= global_t <= grp.end:
                active_group = grp
                break

        if active_group is not None:
            draw.rectangle([90, 1190, 990, 1306], fill=self.BG_VELLUM, outline=self.INK_DARK, width=3)
            draw.rectangle([90, 1190, 104, 1306], fill=self.ACCENT_ORANGE)
            # Highlight active word in orange, others in dark ink
            words = active_group.words
            full_text = active_group.text
            bbox = draw.textbbox((0, 0), full_text, font=self.font_caption)
            tw = bbox[2] - bbox[0]
            start_x = max(120, (self.WIDTH - tw) // 2)
            y_text = 1230

            cursor_x = start_x
            space_w = draw.textbbox((0, 0), " ", font=self.font_caption)[2]
            for w in words:
                is_active = w.start <= global_t <= w.end
                w_bbox = draw.textbbox((0, 0), w.word, font=self.font_caption)
                ww = w_bbox[2] - w_bbox[0]
                if is_active:
                    draw.rectangle(
                        [cursor_x - 6, y_text - 6, cursor_x + ww + 6, y_text + 40],
                        fill=self.ACCENT_ORANGE,
                    )
                    draw.text((cursor_x, y_text), w.word, font=self.font_caption, fill=self.INK_LIGHT)
                else:
                    draw.text((cursor_x, y_text), w.word, font=self.font_caption, fill=self.INK_DARK)
                cursor_x += ww + space_w

        # Footer stamp inside y: [1340, 1740] (structural ledger plate)
        draw.rectangle([90, 1350, 990, 1730], fill=(20, 25, 34), outline=(48, 60, 78), width=2)
        draw.text(
            (118, 1378),
            "ARDHYA NOVRI RAMADHAN, S.T. — QUAD ENGINEERING SHOWCASE",
            font=self.font_footer,
            fill=self.INK_LIGHT,
        )
        summary_rows = [
            ("01  STM32F411 EMG DSP", "4,000 Hz ADC+DMA · 20-500 Hz + 50 Hz Q=30 · r=0.994"),
            ("02  UART FIXTURE KIT", "v0.1.0 · 130 Pytest · 15/15 Fixtures · CRC-32"),
            ("03  BENCHMIND v0.2.0", "Meta AI Hackathon · 1,997/1,997 Frames · -25.5 dB Hum"),
            ("04  PACKING ARENA & WEB", "v0.1.0 2D Heuristics · 3D Signal Lab · ardhyanovri.my.id"),
        ]
        scene_idx = min(3, int(global_t / 6.0))
        for r_i, (r_left, r_right) in enumerate(summary_rows):
            ry = 1432 + r_i * 68
            is_curr = r_i == scene_idx
            row_bg = (30, 42, 56) if is_curr else (23, 29, 40)
            row_bd = self.ACCENT_GREEN if is_curr else (40, 50, 66)
            draw.rectangle([114, ry, 966, ry + 54], fill=row_bg, outline=row_bd, width=2)
            draw.text((130, ry + 14), r_left, font=self.font_mono_xs, fill=self.ACCENT_GREEN if is_curr else self.INK_LIGHT)
            draw.text((435, ry + 14), r_right, font=self.font_mono_xs, fill=self.INK_MUTED)

    def render_frame(self, frame_idx: int) -> Image.Image:
        if isinstance(frame_idx, bool) or not isinstance(frame_idx, int) or frame_idx < 0:
            raise ValueError(f"frame_idx must be a non-negative integer, got {frame_idx!r}")
        global_t = frame_idx / float(self.FPS)
        scene_idx = max(0, min(len(QUAD_SCENES_SPEC) - 1, int(global_t / 6.0)))
        scene = QUAD_SCENES_SPEC[scene_idx]
        local_t = max(0.0, global_t - scene["start_sec"])

        img = self.base_bg.copy()
        draw = ImageDraw.Draw(img)

        self._draw_header(draw, scene, local_t, global_t)

        if scene_idx == 0:
            self._draw_scene1_visual(draw, local_t)
        elif scene_idx == 1:
            self._draw_scene2_visual(draw, local_t)
        elif scene_idx == 2:
            self._draw_scene3_visual(draw, local_t)
        else:
            self._draw_scene4_visual(draw, local_t)

        self._draw_metric_cards(draw, scene, local_t)
        self._draw_captions_and_footer(draw, global_t)
        return img


def generate_quad_showcase(
    output_dir: Union[str, Path] = r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs",
    mp4_filename: str = "ardhya-engineering-quad-showcase-1080x1920.mp4",
    metadata_prefix: str = "ardhya-engineering-quad-showcase",
    *,
    duration_sec: float = 24.0,
    fps: int = 30,
    renderer: Optional[QuadShowcaseRenderer] = None,
    soundtrack_fn: Callable[..., Any] = synthesize_showcase_soundtrack,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    which: Callable[[str], Optional[str]] = shutil.which,
    contact_sheet_fn: Callable[..., Path] = extract_contact_sheet,
    probe_fn: Callable[..., Any] = probe_media,
) -> Dict[str, Any]:
    """Synthesize the 24.0s 1080x1920 30fps Quad Engineering Showcase MP4, SRT, and JSON metadata."""
    if duration_sec <= 0.0 or fps < 1:
        raise ValueError(f"Invalid duration_sec={duration_sec!r} or fps={fps!r}")
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    mp4_path = out_path / mp4_filename
    json_path = out_path / f"{metadata_prefix}.json"
    srt_path = out_path / f"{metadata_prefix}.srt"
    wav_path = out_path / f"{metadata_prefix}-soundtrack.wav"
    sheet_path = out_path / f"{Path(mp4_filename).stem}_sheet.png"

    total_frames = max(1, int(round(duration_sec * fps)))

    # 1. Synthesize 48kHz stereo soundtrack
    soundtrack_manifest = soundtrack_fn(wav_path, duration_sec=duration_sec, bpm=120.0)

    # 2. Build captions and write companion .srt
    caption_groups = build_quad_caption_groups()
    srt_lines: List[str] = []
    for idx, g in enumerate(caption_groups, start=1):
        s_str = _format_srt_time(g.start)
        e_str = _format_srt_time(g.end)
        srt_lines.append(f"{idx}\n{s_str} --> {e_str}\n{g.text}\n")
    srt_path.write_text("\n".join(srt_lines).strip() + "\n", encoding="utf-8")

    # 3. Render frames (1080x1920 RGB24) directly into FFmpeg pipe with 48kHz AAC audio
    ffmpeg_bin = which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        "1080x1920",
        "-r",
        str(fps),
        "-i",
        "-",
        "-i",
        str(wav_path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        str(mp4_path),
    ]

    active_renderer = renderer or QuadShowcaseRenderer()
    proc = popen_factory(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if proc.stdin is None:
        raise RuntimeError("FFmpeg process launched without writable stdin pipe")
    write_err: Optional[BaseException] = None
    try:
        for f_idx in range(total_frames):
            frame_img = active_renderer.render_frame(f_idx)
            proc.stdin.write(frame_img.tobytes())
    except (BrokenPipeError, OSError) as exc:
        write_err = exc
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass

    ret = proc.wait(timeout=120)
    if ret != 0 or write_err is not None:
        raise RuntimeError(
            f"FFmpeg quad showcase encode failed with exit code {ret}"
            + (f" ({write_err})" if write_err else "")
        )

    # 4. Extract contact sheet & probe final media
    contact_sheet_fn(mp4_path, sheet_path, cols=4, rows=2)
    probe_res = probe_fn(mp4_path)

    # 5. Write companion JSON metadata
    metadata: Dict[str, Any] = {
        "title": "Ardhya Novri Ramadhan — Quad Engineering Systems Showcase",
        "author": "Ardhya Novri Ramadhan, S.T.",
        "portfolio_url": "https://ardhyanovri.my.id/",
        "repository_url": "https://github.com/vanovri",
        "output_video": str(mp4_path),
        "companion_json": str(json_path),
        "companion_srt": str(srt_path),
        "contact_sheet": str(sheet_path),
        "soundtrack_wav": str(wav_path),
        "spec": {
            "width": 1080,
            "height": 1920,
            "aspect_ratio": "9:16",
            "fps": fps,
            "duration_sec": duration_sec,
            "total_frames": total_frames,
            "video_codec": probe_res.video_codec,
            "audio_codec": probe_res.audio_codec,
            "audio_sample_rate_hz": 48000,
            "audio_channels": 2,
        },
        "probe_verification": probe_res.to_dict(),
        "soundtrack": soundtrack_manifest.to_dict(),
        "scenes": [
            {
                "scene_id": s["scene_id"],
                "index": s["index"],
                "start_sec": s["start_sec"],
                "end_sec": s["end_sec"],
                "title": s["title"],
                "subtitle": s["subtitle"],
                "metrics": s["metrics"],
            }
            for s in QUAD_SCENES_SPEC
        ],
        "captions": [g.to_dict() for g in caption_groups],
        "flagship_systems": {
            "stm32f411_emg_pipeline": {
                "mcu": "STM32F411CEU6",
                "sensor": "DFRobot SEN0240 Analog EMG (ADC1 PA0)",
                "sampling_rate_hz_nominal": 4000,
                "calibration_samples": 8000,
                "filters": ["Butterworth 2nd-Order HPF 20 Hz", "Butterworth 2nd-Order LPF 500 Hz", "2nd-Order 50 Hz Notch Q=30"],
                "feature_window_ms": 100,
                "feature_window_samples": 400,
                "pearson_r": 0.994114,
                "grip_rms_mv": {"relax": 7.64, "light": 16.10, "medium_rpe5": 38.52, "strong": 52.71},
            },
            "uart_fixture_kit": {
                "version": "v0.1.0",
                "pytest_passed": 130,
                "synthetic_fixtures": "15/15",
                "verification": ["CRC-32", "Framing stress", "Fragmentation & noise injection"],
            },
            "benchmind": {
                "version": "v0.2.0",
                "event": "Meta Global AI Developer Hackathon",
                "uart_frames_recovered": "1,997/1,997",
                "hum_attenuation_db": 25.5,
                "role": "AI root-cause hardware copilot",
            },
            "packing_arena_and_portfolio": {
                "packing_arena_version": "v0.1.0",
                "domain": "https://ardhyanovri.my.id/",
                "features": ["Interactive 2D bin-packing heuristics", "3D WebGL Signal Lab", "Full-stack engineering portfolio"],
            },
        },
    }

    json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata
