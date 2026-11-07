from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from .caption_engine import _format_srt_time
from .contracts import CaptionGroup, WordTimestamp
from .ffmpeg_bridge import extract_contact_sheet, probe_media
from .soundtrack_synth import synthesize_showcase_soundtrack


BENCHMIND_SCENES_SPEC: List[Dict[str, Any]] = [
    {
        "scene_id": "bm_scene_01_problem_hardware",
        "index": 1,
        "start_sec": 0.0,
        "end_sec": 6.0,
        "eyebrow": "SCENE 01 / 04 · META GLOBAL AI DEVELOPER HACKATHON · TEAM 1429535549246922",
        "title": "PROBLEM & STM32F411 HARDWARE SETUP",
        "subtitle": "SEN0240 EMG @ 4,000 Hz ADC+DMA · 50 Hz Mains Hum, +150.25 mV DC Offset & Corrupted UART",
        "badge_top": "META AI HACKATHON",
        "badge_sub": "TEAM ID: 1429535549246922",
        "metrics": [
            {"label": "NOMINAL SAMPLING", "value": "4,000 Hz", "detail": "STM32F411CEU6 ADC1 PA0 + Circular DMA"},
            {"label": "PA0 DC OFFSET", "value": "+150.25 mV", "detail": "Electrode Half-Cell + Bias Drift on PA0"},
            {"label": "NOISE CORRUPTION", "value": "50 Hz + CRC", "detail": "Mains Hum + Fragmented UART Byte Streams"},
        ],
        "ledger_title": "RAW BENCH FAULT TELEMETRY",
        "ledger_lines": [
            "MCU: STM32F411CEU6 (100 MHz Cortex-M4F)",
            "Sensor: DFRobot SEN0240 Surface EMG (PA0)",
            "Naive Parser: 9/1,997 frames (99.5% lost)",
        ],
        "caption_segments": [
            (0.15, 2.95, "STM32F411 captures 4,000 Hz EMG with +150.25 mV offset"),
            (3.05, 5.85, "50 Hz mains hum and UART corruption break naive parsers"),
        ],
    },
    {
        "scene_id": "bm_scene_02_signal_frame_recovery",
        "index": 2,
        "start_sec": 6.0,
        "end_sec": 12.0,
        "eyebrow": "SCENE 02 / 04 · DETERMINISTIC SIGNAL & UART FRAME RECOVERY",
        "title": "1,997 / 1,997 UART RECOVERY & -25.5 dB NOTCH",
        "subtitle": "+1,988 Frames Over Naive Parser · 3 CRC-32 Bit-Flips Isolated [17, 63, 142] · +17.02 dB SNR",
        "badge_top": "SIGNAL RECOVERY",
        "badge_sub": "100% VALID FRAMES",
        "metrics": [
            {"label": "UART RECOVERY", "value": "1,997 / 1,997", "detail": "100% Valid Frames (+1,988 vs Naive Parser)"},
            {"label": "CRC-32 BIT-FLIPS", "value": "[17, 63, 142]", "detail": "3 Corrupted Frames Deterministically Isolated"},
            {"label": "50 Hz ATTENUATION", "value": "-25.5 dB", "detail": "Cascaded Biquad Q=30 · +17.02 dB SNR Gain"},
        ],
        "ledger_title": "RECOVERY & DSP PROOF LEDGER",
        "ledger_lines": [
            "Total Raw Stream: 2,000 frames (1,997 valid)",
            "Isolated CRC-32 Faults: idx [17, 63, 142]",
            "Passband 20-500 Hz + 50 Hz Notch -> +17.02 dB SNR",
        ],
        "caption_segments": [
            (6.15, 8.95, "Recovers 1,997/1,997 valid frames and isolates 3 CRC-32 flips"),
            (9.05, 11.85, "Cascaded biquad notch cuts 50 Hz hum by 25.5 dB (+17.02 dB SNR)"),
        ],
    },
    {
        "scene_id": "bm_scene_03_ai_copilot",
        "index": 3,
        "start_sec": 12.0,
        "end_sec": 18.0,
        "eyebrow": "SCENE 03 / 04 · AI ROOT-CAUSE HARDWARE COPILOT (v0.2.0)",
        "title": "RANKED HYPOTHESES & CITATION GUARDRAILS",
        "subtitle": "RC-1..RC-4 Root-Cause Ranking · Strict E1-E6 / F1-F5 Evidence IDs · PA-1..PA-4 Probe Actions",
        "badge_top": "BENCHMIND v0.2.0",
        "badge_sub": "ZERO UNGROUNDED CLAIMS",
        "metrics": [
            {"label": "HYPOTHESIS LEDGER", "value": "RC-1 .. RC-4", "detail": "Ranked Posterior Fault Isolation Engine"},
            {"label": "EVIDENCE GUARDRAIL", "value": "E1-E6 / F1-F5", "detail": "100% Grounded Telemetry & Firmware Citations"},
            {"label": "PROBE CHECKLIST", "value": "PA-1 .. PA-4", "detail": "Actionable STM32 Oscilloscope & Grounding Steps"},
        ],
        "ledger_title": "GROUNDED COPILOT VERIFICATION",
        "ledger_lines": [
            "Citation Guardrail: Every claim binds E1..E6 / F1..F5",
            "Top Root Cause RC-1: Mains 50 Hz capacitive coupling",
            "Action PA-1: Verify AGND/DGND star point & shielding",
        ],
        "caption_segments": [
            (12.15, 14.95, "BenchMind v0.2.0 ranks RC-1 to RC-4 with E1-E6 citations"),
            (15.05, 17.85, "Generates PA-1 to PA-4 STM32 hardware bench probe actions"),
        ],
    },
    {
        "scene_id": "bm_scene_04_sponsor_stack",
        "index": 4,
        "start_sec": 18.0,
        "end_sec": 24.0,
        "eyebrow": "SCENE 04 / 04 · SPONSOR STACK ARCHITECTURE & PYTEST PROOF",
        "title": "META LLAMA + BASETEN + FIREWORKS + MODAL",
        "subtitle": "Meta Llama / Muse Spark · Baseten Low-Latency · Fireworks JSON Tools · Modal DSP (33/33 PASS)",
        "badge_top": "33 / 33 PYTEST PASS",
        "badge_sub": "4-SPONSOR AI STACK",
        "metrics": [
            {"label": "FOUNDATION & SERVING", "value": "LLAMA + BASETEN", "detail": "Meta Llama / Muse Spark on Baseten TensorRT"},
            {"label": "STRUCTURED TOOLS", "value": "FIREWORKS AI", "detail": "Strict JSON Schema Hypothesis & Citation Calls"},
            {"label": "SERVERLESS DSP & CI", "value": "MODAL · 33 PASS", "detail": "Parallel Replay Worker · 33/33 Pytest Verified"},
        ],
        "ledger_title": "END-TO-END HACKATHON VERIFICATION",
        "ledger_lines": [
            "Meta Global AI Developer Hackathon · Team 1429535549246922",
            "Sponsor Stack: Meta + Baseten + Fireworks AI + Modal",
            "Test Suite: 33/33 pytest PASS · Deterministic Replay",
        ],
        "caption_segments": [
            (18.15, 20.95, "Powered by Meta Llama, Baseten, Fireworks AI, and Modal"),
            (21.05, 23.85, "33/33 pytest pass — Team 1429535549246922 verified"),
        ],
    },
]


REDFLAG_SCENES_SPEC: List[Dict[str, Any]] = [
    {
        "scene_id": "rf_scene_01_problem_scams",
        "index": 1,
        "start_sec": 0.0,
        "end_sec": 6.0,
        "eyebrow": "SCENE 01 / 04 · SEA × OPENAI CODEX HACKATHON · AUTONOMOUS & ADAPTIVE AI",
        "title": "INDONESIAN MARKETPLACE CHAT SCAMS (ID-ScamChat-72)",
        "subtitle": "Fake Courier .apk Resi · Phishing Links · QRIS Refund Traps · Escrow Bypass · Fake CS Urgency",
        "badge_top": "SEA × CODEX",
        "badge_sub": "BENCHMARK: ID-ScamChat-72",
        "metrics": [
            {"label": "BENCHMARK CORPUS", "value": "72 CHATS", "detail": "36 Dev + 36 Holdout Val · 5 Adversarial Scam Vectors"},
            {"label": "GEN 0 BASELINE F1", "value": "0.629 F1", "detail": "Naive Keyword Rules Suffering 11 False Positives"},
            {"label": "BENIGN AMBIGUITY", "value": "11 FP TRAPS", "detail": "Legit Resi, Pusat Resolusi & Official Links Flagged"},
        ],
        "ledger_title": "ADVERSARIAL THREAT TAXONOMY",
        "ledger_lines": [
            "V1: Kurir .apk ('Cek_Resi_JNE.apk') & Link Phishing",
            "V2: QRIS Refund Trap & Direct Transfer Bypass",
            "V3: Benign Lookalikes (Resi JNE/J&T, Pusat Resolusi)",
        ],
        "caption_segments": [
            (0.15, 2.95, "Indonesian marketplace chats face APK resi and QRIS scams"),
            (3.05, 5.85, "Gen 0 rules score 0.629 F1 with 11 false positives on ID-ScamChat-72"),
        ],
    },
    {
        "scene_id": "rf_scene_02_autonomous_loop",
        "index": 2,
        "start_sec": 6.0,
        "end_sec": 12.0,
        "eyebrow": "SCENE 02 / 04 · SELF-EVOLVING WRITE -> RUN -> EVALUATE -> REPAIR LOOP",
        "title": "AUTONOMOUS ERROR CLUSTERING & RULE SYNTHESIS",
        "subtitle": "Zero-Human-Intervention Closed Loop · Automated FP & FN Failure Mode Clustering on Dev/Val",
        "badge_top": "CLOSED-LOOP AGENT",
        "badge_sub": "WRITE · RUN · EVAL · REPAIR",
        "metrics": [
            {"label": "AGENT ARCHITECTURE", "value": "4-STAGE LOOP", "detail": "Write Rules -> Run Suite -> Eval Metrics -> Repair"},
            {"label": "ERROR CLUSTERING", "value": "FP & FN TAXON", "detail": "Auto-Groups Obfuscated Evasions vs Benign Collisions"},
            {"label": "GEN 1 EVOLUTION", "value": "0.824 F1", "detail": "+0.195 F1 Jump After First Autonomous Repair Cycle"},
        ],
        "ledger_title": "AUTONOMOUS TELEMETRY LOOP",
        "ledger_lines": [
            "Stage 1-2: Synthesize candidate detector & execute on 72 chats",
            "Stage 3: Compute Precision, Recall, F1 & cluster FP/FN slices",
            "Stage 4: Patch regex ast & whitelist benign marketplace flows",
        ],
        "caption_segments": [
            (6.15, 8.95, "Autonomous Write-Run-Evaluate-Repair loop clusters FPs and FNs"),
            (9.05, 11.85, "Evolves rule logic without human intervention on dev and val splits"),
        ],
    },
    {
        "scene_id": "rf_scene_03_precision_guardrail",
        "index": 3,
        "start_sec": 12.0,
        "end_sec": 18.0,
        "eyebrow": "SCENE 03 / 04 · PRECISION GUARDRAIL & AUTOMATED SELF-CORRECTION",
        "title": "CANDIDATE 2A ROLLBACK & WHITELIST SYNTHESIS",
        "subtitle": "Rejects Overbroad Candidate 2A (Precision < 1.00) · Synthesizes Obfuscation Regex + Safe Whitelists",
        "badge_top": "GUARDRAIL TRIGGERED",
        "badge_sub": "CANDIDATE 2A ROLLED BACK",
        "metrics": [
            {"label": "REJECTED CANDIDATE", "value": "2A ROLLBACK", "detail": "Precision 0.895 < 1.00 Gate -> Auto-Reverted"},
            {"label": "SAFE WHITELISTS", "value": "PUSAT RESOLUSI", "detail": "Protects Official Courier Resi & Escrow Dispute Flows"},
            {"label": "REPAIRED GEN 2B", "value": "0.936 F1", "detail": "Precision Restored to 1.000 with Obfuscation Regex"},
        ],
        "ledger_title": "SELF-CORRECTION DIFF AUDIT",
        "ledger_lines": [
            "Candidate 2A: Overbroad transfer/link rule caused 2 FPs",
            "Guardrail: Precision < 1.00 rejected automatically",
            "Candidate 2B: Added Pusat Resolusi & courier resi whitelist",
        ],
        "caption_segments": [
            (12.15, 14.95, "Precision guardrail automatically rolls back overbroad Candidate 2A"),
            (15.05, 17.85, "Synthesizes obfuscation regex and Pusat Resolusi whitelists"),
        ],
    },
    {
        "scene_id": "rf_scene_04_verified_convergence",
        "index": 4,
        "start_sec": 18.0,
        "end_sec": 24.0,
        "eyebrow": "SCENE 04 / 04 · VERIFIED CONVERGENCE ON DEV & HOLDOUT VAL",
        "title": "CONVERGENCE TO 1.000 F1 & ZERO FALSE POSITIVES",
        "subtitle": "Gen 0 (0.629, 11 FPs) -> Gen 1 (0.824) -> Gen 2 (0.936) -> Gen 3 (1.000 F1, 0 FPs, 5/5 Pytest PASS)",
        "badge_top": "1.000 F1 · 0 FP",
        "badge_sub": "5 / 5 PYTEST PASS",
        "metrics": [
            {"label": "FINAL CONVERGENCE", "value": "1.000 F1", "detail": "100% Precision & 100% Recall on Dev + Holdout Val"},
            {"label": "FALSE POSITIVES", "value": "11 -> 0 FPs", "detail": "Complete Elimination of Benign Buyer/Seller Friction"},
            {"label": "TOTAL F1 GAIN", "value": "+0.371 F1", "detail": "0.629 -> 1.000 Across 3 Generations · 5/5 Pytest PASS"},
        ],
        "ledger_title": "FINAL EVOLUTION LEDGER",
        "ledger_lines": [
            "Gen 0: 0.629 F1 (11 FP) -> Gen 1: 0.824 F1 (4 FP)",
            "Gen 2A: Rolled Back -> Gen 2B: 0.936 F1 (0 FP)",
            "Gen 3: 1.000 F1 (0 FP, 0 FN) · 5/5 pytest PASS",
        ],
        "caption_segments": [
            (18.15, 20.95, "F1 converges from 0.629 to 0.824, 0.936, and 1.000 in Gen 3"),
            (21.05, 23.85, "Zero false positives, +0.371 F1 gain, and 5/5 pytest pass"),
        ],
    },
]


def build_scene_caption_groups(scenes_spec: List[Dict[str, Any]], prefix: str) -> List[CaptionGroup]:
    """Build deterministic word-timed CaptionGroup list from a 4-scene spec."""
    groups: List[CaptionGroup] = []
    grp_idx = 1
    for scene in scenes_spec:
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
                    id=f"{prefix}_cg_{grp_idx:02d}",
                    text=text,
                    start=seg_start,
                    end=seg_end,
                    words=words,
                    safe_box={"x": 56, "y": 852, "w": 1174, "h": 88},
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
    f_dir = Path(fonts_dir)
    for name in candidates:
        p = f_dir / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


class WidescreenHackathonRenderer:
    """Base 1920x1080 30fps Widescreen Engineering Pitch Renderer."""

    WIDTH = 1920
    HEIGHT = 1080
    FPS = 30
    DURATION_SEC = 24.0
    TOTAL_FRAMES = 720

    # Industrial Oscilloscope & Drafting Vellum Palette
    BG_DARK = (15, 19, 26)          # #0F131A
    BG_PANEL = (23, 29, 40)         # #171D28
    BG_CARD = (19, 25, 35)          # #131923
    BG_VELLUM = (244, 241, 234)     # #F4F1EA
    INK_LIGHT = (244, 241, 234)     # #F4F1EA
    INK_MUTED = (148, 163, 184)     # #94A3B8
    INK_DARK = (17, 21, 28)         # #11151C
    ACCENT_ORANGE = (255, 77, 28)   # #FF4D1C
    ACCENT_GREEN = (16, 185, 129)   # #10B981
    ACCENT_CYAN = (56, 189, 248)    # #38BDF8
    ACCENT_AMBER = (245, 158, 11)   # #F59E0B
    ACCENT_RED = (239, 68, 68)      # #EF4444
    ACCENT_PURPLE = (168, 85, 247)  # #A855F7
    GRID_COLOR = (28, 36, 48)

    def __init__(
        self,
        scenes_spec: List[Dict[str, Any]],
        caption_prefix: str,
        footer_project_tag: str,
        roadmap_items: List[Tuple[str, str]],
        primary_accent: Tuple[int, int, int] = (255, 77, 28),
        *,
        font_loader: Optional[Callable[[List[str], int], Any]] = None,
    ) -> None:
        self.scenes_spec = scenes_spec
        self.caption_groups = build_scene_caption_groups(scenes_spec, caption_prefix)
        self.footer_project_tag = footer_project_tag
        self.roadmap_items = roadmap_items
        self.primary_accent = primary_accent

        load_fn = font_loader or _load_font
        self.font_eyebrow = load_fn(["consolab.ttf", "arialbd.ttf"], 21)
        self.font_title = load_fn(["bahnschrift.ttf", "segoeuib.ttf", "arialbd.ttf"], 42)
        self.font_subtitle = load_fn(["segoeuib.ttf", "arialbd.ttf"], 22)
        self.font_badge_lg = load_fn(["consolab.ttf", "arialbd.ttf"], 22)
        self.font_badge_sm = load_fn(["consola.ttf", "arial.ttf"], 17)
        self.font_metric_val = load_fn(["consolab.ttf", "arialbd.ttf"], 34)
        self.font_metric_lbl = load_fn(["consolab.ttf", "arialbd.ttf"], 18)
        self.font_metric_sub = load_fn(["segoeui.ttf", "arial.ttf"], 18)
        self.font_panel_hdr = load_fn(["consolab.ttf", "arialbd.ttf"], 20)
        self.font_mono_md = load_fn(["consolab.ttf", "consola.ttf"], 19)
        self.font_mono_sm = load_fn(["consola.ttf", "arial.ttf"], 17)
        self.font_mono_xs = load_fn(["consola.ttf", "arial.ttf"], 15)
        self.font_caption = load_fn(["segoeuib.ttf", "arialbd.ttf"], 26)

        # Pre-render 1920x1080 engineering grid plate
        self.base_bg = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_DARK)
        draw = ImageDraw.Draw(self.base_bg)
        for x in range(0, self.WIDTH, 32):
            draw.line([(x, 0), (x, self.HEIGHT)], fill=self.GRID_COLOR, width=1)
        for y in range(0, self.HEIGHT, 32):
            draw.line([(0, y), (self.WIDTH, y)], fill=self.GRID_COLOR, width=1)
        # Outer structural frame rail
        draw.rectangle([32, 24, 1888, 1056], outline=(44, 56, 74), width=2)

    @staticmethod
    def _ease_out_cubic(x: float) -> float:
        x = max(0.0, min(1.0, x))
        return 1.0 - (1.0 - x) ** 3

    def _draw_chrome(
        self,
        draw: ImageDraw.ImageDraw,
        scene: Dict[str, Any],
        local_t: float,
        global_t: float,
    ) -> None:
        enter = self._ease_out_cubic(local_t / 0.35)
        y_off = int((1.0 - enter) * -12)

        # 1. Top Telemetry Bar: x=[52, 1868], y=[40, 86]
        draw.rectangle([52, 40, 1868, 86], fill=self.BG_PANEL, outline=(56, 70, 92), width=2)
        draw.rectangle([52, 40, 66, 86], fill=self.primary_accent)
        draw.text((82, 51), scene["eyebrow"], font=self.font_eyebrow, fill=self.INK_LIGHT)

        tc_str = f"1920x1080 30FPS  |  T+{global_t:05.2f}s / 24.00s"
        bbox_tc = draw.textbbox((0, 0), tc_str, font=self.font_eyebrow)
        tw_tc = bbox_tc[2] - bbox_tc[0]
        draw.text((1848 - tw_tc, 51), tc_str, font=self.font_eyebrow, fill=self.ACCENT_GREEN)

        # 2. 4-Segment Progress Bar: x=[52, 1868], y=[94, 104]
        seg_w = (1868 - 52 - 36) // 4
        for i in range(4):
            sx0 = 52 + i * (seg_w + 12)
            sx1 = sx0 + seg_w
            draw.rectangle([sx0, 94, sx1, 104], fill=(34, 43, 58))
            if i + 1 < scene["index"]:
                draw.rectangle([sx0, 94, sx1, 104], fill=self.ACCENT_GREEN)
            elif i + 1 == scene["index"]:
                prog = max(0.0, min(1.0, local_t / 6.0))
                draw.rectangle([sx0, 94, sx0 + int(seg_w * prog), 104], fill=self.primary_accent)

        # 3. Title & Subtitle + Right Badge Box: y=[116, 212]
        draw.text((52, 118 + y_off), scene["title"], font=self.font_title, fill=self.INK_LIGHT)
        draw.text((52, 172 + y_off), scene["subtitle"], font=self.font_subtitle, fill=self.INK_MUTED)

        # Right Event Badge Card: x=[1440, 1868], y=[116, 206]
        draw.rectangle([1440, 116, 1868, 206], fill=self.BG_PANEL, outline=self.primary_accent, width=2)
        draw.rectangle([1440, 116, 1452, 206], fill=self.primary_accent)
        draw.text((1468, 128), scene["badge_top"], font=self.font_badge_lg, fill=self.INK_LIGHT)
        draw.text((1468, 162), scene["badge_sub"], font=self.font_badge_sm, fill=self.ACCENT_GREEN)

    def _draw_right_column(
        self,
        draw: ImageDraw.ImageDraw,
        scene: Dict[str, Any],
        local_t: float,
    ) -> None:
        # Right column x=[1248, 1868], y=[220, 836]
        rx0, rx1 = 1248, 1868
        metrics = scene["metrics"]
        for idx, m in enumerate(metrics):
            delay = 0.10 + idx * 0.15
            prog = self._ease_out_cubic((local_t - delay) / 0.40)
            x_shift = int((1.0 - prog) * 24)
            cy0 = 220 + idx * 144
            cy1 = cy0 + 130
            cx0 = rx0 + x_shift
            is_hero = idx == 0
            bd_col = self.primary_accent if is_hero else self.ACCENT_GREEN
            draw.rectangle([cx0, cy0, rx1, cy1], fill=self.BG_PANEL, outline=bd_col, width=2)
            draw.rectangle([cx0, cy0, cx0 + 10, cy1], fill=bd_col)

            draw.text((cx0 + 24, cy0 + 14), m["label"], font=self.font_metric_lbl, fill=self.INK_MUTED)
            val_col = self.primary_accent if is_hero else self.ACCENT_GREEN
            draw.text((cx0 + 24, cy0 + 42), m["value"], font=self.font_metric_val, fill=val_col)
            draw.text((cx0 + 24, cy0 + 90), m["detail"], font=self.font_metric_sub, fill=self.INK_LIGHT)

        # Ledger Box at y=[652, 836]
        ly0, ly1 = 652, 836
        draw.rectangle([rx0, ly0, rx1, ly1], fill=(18, 24, 34), outline=(58, 74, 96), width=2)
        draw.rectangle([rx0, ly0, rx1, ly0 + 38], fill=(28, 37, 52))
        draw.text((rx0 + 18, ly0 + 9), scene["ledger_title"], font=self.font_metric_lbl, fill=self.ACCENT_CYAN)
        for idx, line in enumerate(scene["ledger_lines"]):
            draw.text((rx0 + 18, ly0 + 50 + idx * 40), f"▸ {line}", font=self.font_mono_sm, fill=self.INK_LIGHT)

    def _draw_bottom_bar(self, draw: ImageDraw.ImageDraw, global_t: float) -> None:
        # 1. Word-timed Vellum Caption Plate: x=[52, 1230], y=[850, 938]
        active_group: CaptionGroup | None = None
        for grp in self.caption_groups:
            if grp.start <= global_t <= grp.end:
                active_group = grp
                break

        draw.rectangle([52, 850, 1230, 938], fill=self.BG_VELLUM, outline=self.INK_DARK, width=3)
        draw.rectangle([52, 850, 66, 938], fill=self.primary_accent)
        if active_group is not None:
            words = active_group.words
            full_text = active_group.text
            bbox = draw.textbbox((0, 0), full_text, font=self.font_caption)
            tw = bbox[2] - bbox[0]
            start_x = max(84, 52 + (1178 - tw) // 2)
            y_text = 878
            cursor_x = start_x
            space_w = draw.textbbox((0, 0), " ", font=self.font_caption)[2]
            for w in words:
                is_act = w.start <= global_t <= w.end
                w_bbox = draw.textbbox((0, 0), w.word, font=self.font_caption)
                ww = w_bbox[2] - w_bbox[0]
                if is_act:
                    draw.rectangle(
                        [cursor_x - 5, y_text - 4, cursor_x + ww + 5, y_text + 34],
                        fill=self.primary_accent,
                    )
                    draw.text((cursor_x, y_text), w.word, font=self.font_caption, fill=self.INK_LIGHT)
                else:
                    draw.text((cursor_x, y_text), w.word, font=self.font_caption, fill=self.INK_DARK)
                cursor_x += ww + space_w

        # 2. Author & Verification Stamp Box: x=[1248, 1868], y=[850, 938]
        draw.rectangle([1248, 850, 1868, 938], fill=self.BG_PANEL, outline=(56, 70, 92), width=2)
        draw.text((1268, 862), self.footer_project_tag, font=self.font_mono_md, fill=self.INK_LIGHT)
        draw.text(
            (1268, 896),
            "Ardhya Novri Ramadhan, S.T. · github.com/vanovri",
            font=self.font_mono_sm,
            fill=self.ACCENT_GREEN,
        )

        # 3. 4-Scene Roadmap Strip: x=[52, 1868], y=[952, 1036]
        scene_idx = min(3, int(global_t / 6.0))
        card_w = (1868 - 52 - 36) // 4
        for idx, (rm_title, rm_sub) in enumerate(self.roadmap_items):
            cx0 = 52 + idx * (card_w + 12)
            cx1 = cx0 + card_w
            is_curr = idx == scene_idx
            bg_c = (28, 40, 56) if is_curr else (19, 25, 35)
            bd_c = self.primary_accent if is_curr else (42, 54, 70)
            draw.rectangle([cx0, 952, cx1, 1036], fill=bg_c, outline=bd_c, width=2)
            draw.text(
                (cx0 + 16, 964),
                rm_title,
                font=self.font_mono_sm,
                fill=self.ACCENT_GREEN if is_curr else self.INK_LIGHT,
            )
            draw.text((cx0 + 16, 996), rm_sub, font=self.font_mono_xs, fill=self.INK_MUTED)


class BenchMindHackathonRenderer(WidescreenHackathonRenderer):
    """1920x1080 30fps Widescreen Renderer for BenchMind v0.2.0 (Meta Global AI Hackathon)."""

    def __init__(
        self,
        *,
        font_loader: Optional[Callable[[List[str], int], Any]] = None,
    ) -> None:
        roadmap = [
            ("01 · HARDWARE & NOISE", "STM32F411 4kHz · +150.25mV · 50Hz"),
            ("02 · SIGNAL RECOVERY", "1,997/1,997 Frames · -25.5dB Notch"),
            ("03 · AI COPILOT v0.2.0", "RC-1..RC-4 · E1-E6/F1-F5 · PA-1..PA-4"),
            ("04 · SPONSOR STACK", "Llama + Baseten + Fireworks + Modal"),
        ]
        super().__init__(
            scenes_spec=BENCHMIND_SCENES_SPEC,
            caption_prefix="benchmind",
            footer_project_tag="BENCHMIND v0.2.0 · META AI HACKATHON",
            roadmap_items=roadmap,
            primary_accent=self.ACCENT_ORANGE,
            font_loader=font_loader,
        )

    def _draw_scene1(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        # Left Canvas: x=[52, 1230], y=[220, 836]
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        # Top Oscilloscope Panel: Raw PA0 EMG corrupted by 50 Hz mains hum & +150.25 mV DC offset
        ox0, oy0, ox1, oy1 = vx0 + 20, vy0 + 18, vx1 - 20, vy0 + 365
        draw.rectangle([ox0, oy0, ox1, oy1], fill=(10, 14, 20), outline=(44, 56, 74), width=1)
        for gx in range(ox0 + 70, ox1, 70):
            draw.line([(gx, oy0), (gx, oy1)], fill=(22, 30, 42), width=1)
        for gy in range(oy0 + 45, oy1, 45):
            draw.line([(ox0, gy), (ox1, gy)], fill=(22, 30, 42), width=1)

        # Nominal 0 mV reference vs shifted +150.25 mV DC baseline
        zero_y = oy1 - 65
        dc_y = oy0 + 145
        draw.line([(ox0, zero_y), (ox1, zero_y)], fill=(70, 85, 110), width=1)
        draw.text((ox0 + 14, zero_y - 22), "0.00 mV NOMINAL REF", font=self.font_mono_xs, fill=self.INK_MUTED)

        draw.line([(ox0, dc_y), (ox1, dc_y)], fill=self.ACCENT_AMBER, width=2)
        draw.text(
            (ox0 + 14, oy0 + 12),
            "CH1: STM32F411 PA0 RAW ADC+DMA (4,000 Hz) — +150.25 mV DC OFFSET + 50 Hz MAINS HUM",
            font=self.font_mono_sm,
            fill=self.ACCENT_ORANGE,
        )
        draw.text(
            (ox1 - 310, dc_y - 24),
            "DC OFFSET: +150.25 mV",
            font=self.font_mono_xs,
            fill=self.ACCENT_AMBER,
        )

        pts: List[Tuple[int, int]] = []
        phase = local_t * 6.0
        n_pts = 220
        for i in range(n_pts):
            u = i / float(n_pts - 1)
            px = ox0 + 16 + int((ox1 - ox0 - 32) * u)
            burst = math.exp(-((u - 0.30) / 0.10) ** 2) + 0.9 * math.exp(-((u - 0.72) / 0.11) ** 2)
            emg = burst * (
                18.0 * math.sin(2.0 * math.pi * 29.0 * u + phase * 2.0)
                + 12.0 * math.cos(2.0 * math.pi * 47.0 * u - phase * 1.5)
            )
            hum_50hz = 42.0 * math.sin(2.0 * math.pi * 10.0 * u + phase * 1.4)
            py = int(dc_y - (emg + hum_50hz))
            pts.append((px, max(oy0 + 42, min(oy1 - 14, py))))
        draw.line(pts, fill=self.ACCENT_ORANGE, width=3)

        # Bottom Panel: Corrupted UART Byte Stream & Naive Parser Collapse
        ux0, uy0, ux1, uy1 = vx0 + 20, vy0 + 382, vx1 - 20, vy1 - 18
        draw.rectangle([ux0, uy0, ux1, uy1], fill=(16, 21, 30), outline=(56, 70, 92), width=1)
        draw.text(
            (ux0 + 16, uy0 + 12),
            "CORRUPTED DMA-UART TELEMETRY STREAM (NAIVE PARSER DROPS 1,988 / 1,997 FRAMES)",
            font=self.font_mono_sm,
            fill=self.ACCENT_CYAN,
        )

        packets = [
            ("PKT #0016 [FRAG]", "AA 55 00 10 8F C2 ... [SPLIT CHUNK BOUNDARY]", "NAIVE: DROPPED", self.ACCENT_RED),
            ("PKT #0017 [CRC!]", "AA 55 00 11 94 1A CRC32:BAD_BITFLIP_IDX_17", "CRC-32 FAULT", self.ACCENT_ORANGE),
            ("PKT #0063 [CRC!]", "AA 55 00 3F 7E 09 CRC32:BAD_BITFLIP_IDX_63", "CRC-32 FAULT", self.ACCENT_ORANGE),
            ("PKT #0142 [CRC!]", "AA 55 00 8E 6B 55 CRC32:BAD_BITFLIP_IDX_142", "CRC-32 FAULT", self.ACCENT_ORANGE),
        ]
        for idx, (tag, hex_str, status, col) in enumerate(packets):
            ry = uy0 + 46 + idx * 42
            draw.rectangle([ux0 + 16, ry, ux1 - 16, ry + 34], fill=(22, 29, 42), outline=(42, 54, 72), width=1)
            draw.text((ux0 + 28, ry + 7), tag, font=self.font_mono_xs, fill=self.ACCENT_AMBER)
            draw.text((ux0 + 240, ry + 7), hex_str, font=self.font_mono_xs, fill=self.INK_LIGHT)
            draw.text((ux1 - 210, ry + 7), status, font=self.font_mono_xs, fill=col)

    def _draw_scene2(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        prog = self._ease_out_cubic(min(1.0, local_t / 1.8))

        # Left Sub-Panel: UART Frame Recovery Comparison + Bit-Flip Isolation
        lx0, ly0, lx1, ly1 = vx0 + 20, vy0 + 20, vx0 + 575, vy1 - 20
        draw.rectangle([lx0, ly0, lx1, ly1], fill=(16, 22, 32), outline=(52, 68, 90), width=1)
        draw.text(
            (lx0 + 16, ly0 + 14),
            "DETERMINISTIC UART RESYNC ENGINE",
            font=self.font_panel_hdr,
            fill=self.ACCENT_CYAN,
        )

        # Bar comparison: Naive Parser (9/1997) vs BenchMind Resync (1,997/1,997)
        rec_count = int(round(1997 * prog))
        draw.text((lx0 + 18, ly0 + 60), "Naive Line Parser: 9 / 1,997 (0.45%)", font=self.font_mono_sm, fill=self.INK_MUTED)
        draw.rectangle([lx0 + 18, ly0 + 90, lx1 - 18, ly0 + 122], fill=(28, 36, 48))
        draw.rectangle([lx0 + 18, ly0 + 90, lx0 + 30, ly0 + 122], fill=self.ACCENT_RED)

        draw.text(
            (lx0 + 18, ly0 + 144),
            f"BenchMind Resync: {rec_count:,} / 1,997 (100.0%) [+1,988]",
            font=self.font_mono_sm,
            fill=self.ACCENT_GREEN,
        )
        draw.rectangle([lx0 + 18, ly0 + 174, lx1 - 18, ly0 + 206], fill=(28, 36, 48))
        bar_w = int((lx1 - lx0 - 36) * prog)
        draw.rectangle([lx0 + 18, ly0 + 174, lx0 + 18 + bar_w, ly0 + 206], fill=self.ACCENT_GREEN)

        # CRC-32 Bit-Flip Isolation Table
        draw.text(
            (lx0 + 18, ly0 + 236),
            "ISOLATED CRC-32 BIT-FLIP INDICES (3 / 2,000):",
            font=self.font_mono_sm,
            fill=self.ACCENT_AMBER,
        )
        flips = [
            ("Frame idx = 17", "CRC32 Mismatch -> Quarantined & Logged (E2)"),
            ("Frame idx = 63", "CRC32 Mismatch -> Quarantined & Logged (E2)"),
            ("Frame idx = 142", "CRC32 Mismatch -> Quarantined & Logged (E2)"),
        ]
        for idx, (f_idx, f_desc) in enumerate(flips):
            fy = ly0 + 272 + idx * 54
            draw.rectangle([lx0 + 18, fy, lx1 - 18, fy + 44], fill=(24, 31, 44), outline=self.ACCENT_AMBER, width=1)
            draw.text((lx0 + 30, fy + 12), f_idx, font=self.font_mono_xs, fill=self.ACCENT_ORANGE)
            draw.text((lx0 + 175, fy + 12), f_desc, font=self.font_mono_xs, fill=self.INK_LIGHT)

        # Bottom summary pill inside left sub-panel
        draw.rectangle([lx0 + 18, ly1 - 108, lx1 - 18, ly1 - 20], fill=(14, 36, 30), outline=self.ACCENT_GREEN, width=2)
        draw.text((lx0 + 32, ly1 - 92), "ZERO SILENT CORRUPTION · 100% VALID RECOVERY", font=self.font_mono_sm, fill=self.ACCENT_GREEN)
        draw.text((lx0 + 32, ly1 - 56), "DC Offset (-150.25 mV) & Clipping Monitored", font=self.font_mono_xs, fill=self.INK_LIGHT)

        # Right Sub-Panel: Bode 50 Hz Notch Canyon (-25.5 dB) & +17.02 dB SNR Gain
        rx0, ry0, rx1, ry1 = vx0 + 595, vy0 + 20, vx1 - 20, vy1 - 20
        draw.rectangle([rx0, ry0, rx1, ry1], fill=(10, 14, 20), outline=(52, 68, 90), width=1)
        draw.text(
            (rx0 + 16, ry0 + 14),
            "CASCADED BIQUAD: -25.5 dB @ 50 Hz (+17.02 dB SNR)",
            font=self.font_panel_hdr,
            fill=self.ACCENT_GREEN,
        )

        # Draw Bode Magnitude plot
        gx0, gy0, gx1, gy1 = rx0 + 24, ry0 + 58, rx1 - 24, ry0 + 360
        draw.rectangle([gx0, gy0, gx1, gy1], fill=(14, 19, 27), outline=(40, 52, 68), width=1)
        for y_grid in range(gy0 + 50, gy1, 50):
            draw.line([(gx0, y_grid), (gx1, y_grid)], fill=(24, 32, 44), width=1)

        curve_pts: List[Tuple[int, int]] = []
        for i in range(140):
            u = i / 139.0
            px = gx0 + 12 + int((gx1 - gx0 - 24) * u)
            hpf = -22.0 * math.exp(-u / 0.07)
            lpf = -20.0 * math.exp(-(1.0 - u) / 0.08)
            notch = -25.5 * prog * math.exp(-((u - 0.35) / 0.026) ** 2)
            db = hpf + lpf + notch
            py = gy0 + 48 - int((db / 30.0) * 210.0)
            curve_pts.append((px, max(gy0 + 20, min(gy1 - 16, py))))
        draw.line(curve_pts, fill=self.ACCENT_GREEN, width=4)

        nx = gx0 + 12 + int((gx1 - gx0 - 24) * 0.35)
        ny = gy0 + 48 + int((25.5 * prog / 30.0) * 210.0)
        draw.ellipse([nx - 7, ny - 7, nx + 7, ny + 7], fill=self.ACCENT_ORANGE)
        draw.text((nx + 14, ny - 12), "-25.5 dB @ 50.0 Hz (Q=30)", font=self.font_mono_sm, fill=self.ACCENT_ORANGE)

        # Clean Filtered EMG Output Preview at bottom of right sub-panel
        cx0, cy0, cx1, cy1 = rx0 + 24, ry0 + 380, rx1 - 24, ry1 - 20
        draw.rectangle([cx0, cy0, cx1, cy1], fill=(14, 24, 24), outline=self.ACCENT_GREEN, width=1)
        draw.text(
            (cx0 + 14, cy0 + 10),
            "RECOVERED EMG ENVELOPE (SNR GAIN: +17.02 dB)",
            font=self.font_mono_xs,
            fill=self.ACCENT_GREEN,
        )
        clean_pts: List[Tuple[int, int]] = []
        mid_cy = (cy0 + cy1) // 2 + 12
        for i in range(140):
            u = i / 139.0
            px = cx0 + 12 + int((cx1 - cx0 - 24) * u)
            burst = math.exp(-((u - 0.30) / 0.09) ** 2) + 0.85 * math.exp(-((u - 0.72) / 0.10) ** 2)
            sig = burst * 42.0 * math.sin(2.0 * math.pi * 24.0 * u + local_t * 8.0)
            clean_pts.append((px, int(mid_cy - sig)))
        draw.line(clean_pts, fill=self.ACCENT_GREEN, width=3)

    def _draw_scene3(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "AI ROOT-CAUSE HARDWARE COPILOT (v0.2.0) — RANKED HYPOTHESES & CITATION GUARDRAILS",
            font=self.font_panel_hdr,
            fill=self.ACCENT_ORANGE,
        )

        # 4 Ranked Hypotheses RC-1..RC-4 on left half
        hypotheses = [
            ("RC-1 [P=0.46]", "50 Hz Mains Capacitive Coupling on PA0 Lead", "Cites: [E1, E4, F2]", self.ACCENT_ORANGE),
            ("RC-2 [P=0.28]", "PA0 Half-Cell Electrode +150.25 mV DC Bias", "Cites: [E3, F1, F4]", self.ACCENT_AMBER),
            ("RC-3 [P=0.18]", "DMA-UART Framing Split & 3 CRC-32 Bit-Flips", "Cites: [E2, E5, F3]", self.ACCENT_CYAN),
            ("RC-4 [P=0.08]", "ADC High-Gain Saturation Clipping (>3.28 V)", "Cites: [E6, F5]", self.ACCENT_GREEN),
        ]
        for idx, (rc_id, rc_title, rc_cites, rc_col) in enumerate(hypotheses):
            hy0 = vy0 + 56 + idx * 82
            hy1 = hy0 + 70
            draw.rectangle([vx0 + 20, hy0, vx0 + 680, hy1], fill=(19, 25, 36), outline=rc_col, width=2)
            draw.rectangle([vx0 + 20, hy0, vx0 + 30, hy1], fill=rc_col)
            draw.text((vx0 + 42, hy0 + 10), f"{rc_id}  {rc_title}", font=self.font_mono_sm, fill=self.INK_LIGHT)
            draw.text((vx0 + 42, hy0 + 38), f"Verified Guardrail Citations -> {rc_cites}", font=self.font_mono_xs, fill=rc_col)

        # Right sub-panel inside canvas: PA-1..PA-4 STM32 Bench Probe Checklist
        px0, py0, px1, py1 = vx0 + 700, vy0 + 56, vx1 - 20, vy0 + 372
        draw.rectangle([px0, py0, px1, py1], fill=self.BG_VELLUM, outline=self.INK_DARK, width=2)
        draw.rectangle([px0, py0, px1, py0 + 40], fill=self.ACCENT_ORANGE)
        draw.text((px0 + 14, py0 + 10), "STM32 BENCH PROBE CHECKLIST (PA-1..PA-4)", font=self.font_mono_xs, fill=self.INK_LIGHT)

        probes = [
            ("PA-1", "Scope PA0 AC-coupled FFT @ 50.0 Hz & check shield"),
            ("PA-2", "Measure SEN0240 Vref & PA0 +150.25 mV DC bias"),
            ("PA-3", "Inspect USART2 TX/RX ground return & DMA circular"),
            ("PA-4", "Enable Q=30 50 Hz notch + HPF 20 Hz on STM32 DSP"),
        ]
        for idx, (pa_id, pa_desc) in enumerate(probes):
            py_row = py0 + 54 + idx * 62
            draw.rectangle([px0 + 12, py_row, px1 - 12, py_row + 50], fill=(232, 228, 218), outline=(180, 174, 162), width=1)
            draw.text((px0 + 22, py_row + 15), f"[✓] {pa_id}: {pa_desc}", font=self.font_mono_xs, fill=self.INK_DARK)

        # Bottom Guardrail Strip: E1-E6 Telemetry Evidence + F1-F5 Firmware Rules
        gx0, gy0, gx1, gy1 = vx0 + 20, vy0 + 392, vx1 - 20, vy1 - 18
        draw.rectangle([gx0, gy0, gx1, gy1], fill=(16, 24, 34), outline=self.ACCENT_GREEN, width=2)
        draw.text(
            (gx0 + 18, gy0 + 14),
            "STRICT EVIDENCE CITATION GUARDRAIL — 0 UNGROUNDED CLAIMS ALLOWED",
            font=self.font_mono_md,
            fill=self.ACCENT_GREEN,
        )
        ev_pills = [
            "E1: 50Hz PSD -25.5dB",
            "E2: CRC Flips [17,63,142]",
            "E3: PA0 +150.25mV DC",
            "E4: +17.02dB SNR Gain",
            "E5: 1,997/1,997 Frames",
            "E6: Clipping Ratio 0.4%",
            "F1: ADC1_PA0_DMA",
            "F2: BIQUAD_NOTCH_50HZ",
            "F3: UART_CRC32_SYNC",
            "F4: CALIB_8000_SAMPLES",
            "F5: WINDOW_100MS_RMS",
        ]
        for idx, pill in enumerate(ev_pills):
            col_i = idx % 4
            row_i = idx // 4
            bx = gx0 + 18 + col_i * 280
            by = gy0 + 52 + row_i * 46
            draw.rectangle([bx, by, bx + 266, by + 36], fill=(24, 34, 48), outline=self.ACCENT_CYAN, width=1)
            draw.text((bx + 10, by + 9), pill, font=self.font_mono_xs, fill=self.INK_LIGHT)

    def _draw_scene4(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "MULTI-SPONSOR AI & SERVERLESS DSP ARCHITECTURE — META GLOBAL AI HACKATHON",
            font=self.font_panel_hdr,
            fill=self.ACCENT_CYAN,
        )

        # 2x2 Sponsor Architecture Grid inside Left Canvas
        cards = [
            (
                "01 · META LLAMA / MUSE SPARK",
                "Foundation Reasoning & Hardware Fault Synthesis",
                [
                    "• Multi-hypothesis root-cause reasoning (RC-1..RC-4)",
                    "• Grounded hardware domain adaptation for STM32 EMG",
                    "• Team ID: 1429535549246922 verified integration",
                ],
                self.ACCENT_CYAN,
            ),
            (
                "02 · BASETEN LOW-LATENCY INFERENCE",
                "High-Throughput Dedicated Model Serving Endpoint",
                [
                    "• Sub-second streaming diagnostic copilot responses",
                    "• Automatic fallback & deterministic latency telemetry",
                    "• Production-grade model routing & health probes",
                ],
                self.ACCENT_GREEN,
            ),
            (
                "03 · FIREWORKS AI JSON TOOL-CALLING",
                "Strict Schema Validation & Citation Guardrails",
                [
                    "• Enforces E1-E6 & F1-F5 citation ID bindings",
                    "• Structured JSON output for PA-1..PA-4 probe checklists",
                    "• Zero hallucinated register names or unverified claims",
                ],
                self.ACCENT_ORANGE,
            ),
            (
                "04 · MODAL SERVERLESS DSP REPLAY",
                "Cloud Batch Signal Recovery & 33/33 Pytest Suite",
                [
                    "• Replays 4,000 Hz DMA stream -> 1,997/1,997 frames",
                    "• Executes cascaded Butterworth + 50 Hz Q=30 notch",
                    "• 33/33 pytest PASS across full hardware/AI pipeline",
                ],
                self.ACCENT_PURPLE,
            ),
        ]

        cw = (vx1 - vx0 - 60) // 2
        ch = 215
        for idx, (c_title, c_sub, c_bullets, c_col) in enumerate(cards):
            gx = idx % 2
            gy = idx // 2
            cx0 = vx0 + 20 + gx * (cw + 20)
            cy0 = vy0 + 56 + gy * (ch + 18)
            cx1 = cx0 + cw
            cy1 = cy0 + ch
            draw.rectangle([cx0, cy0, cx1, cy1], fill=(18, 24, 35), outline=c_col, width=2)
            draw.rectangle([cx0, cy0, cx1, cy0 + 38], fill=(25, 33, 48))
            draw.text((cx0 + 14, cy0 + 9), c_title, font=self.font_mono_sm, fill=c_col)
            draw.text((cx0 + 14, cy0 + 48), c_sub, font=self.font_mono_xs, fill=self.INK_MUTED)
            for b_i, b_txt in enumerate(c_bullets):
                draw.text((cx0 + 14, cy0 + 82 + b_i * 38), b_txt, font=self.font_mono_xs, fill=self.INK_LIGHT)

        # Bottom Verification Banner inside canvas
        bx0, by0, bx1, by1 = vx0 + 20, vy0 + 516, vx1 - 20, vy1 - 16
        draw.rectangle([bx0, by0, bx1, by1], fill=(14, 36, 30), outline=self.ACCENT_GREEN, width=2)
        draw.text(
            (bx0 + 20, by0 + 14),
            "PYTEST VERIFICATION: 33 / 33 PASSED  |  1,997 / 1,997 FRAMES  |  -25.5 dB NOTCH  |  +17.02 dB SNR",
            font=self.font_mono_md,
            fill=self.ACCENT_GREEN,
        )
        draw.text(
            (bx0 + 20, by0 + 48),
            "Meta Global AI Developer Hackathon Submission · Team ID 1429535549246922 · Ardhya Novri Ramadhan, S.T.",
            font=self.font_mono_sm,
            fill=self.INK_LIGHT,
        )

    def render_frame(self, frame_idx: int) -> Image.Image:
        if isinstance(frame_idx, bool) or not isinstance(frame_idx, int) or frame_idx < 0:
            raise ValueError(f"frame_idx must be a non-negative integer, got {frame_idx!r}")
        global_t = frame_idx / float(self.FPS)
        scene_idx = max(0, min(len(self.scenes_spec) - 1, int(global_t / 6.0)))
        scene = self.scenes_spec[scene_idx]
        local_t = max(0.0, global_t - scene["start_sec"])

        img = self.base_bg.copy()
        draw = ImageDraw.Draw(img)

        self._draw_chrome(draw, scene, local_t, global_t)
        if scene_idx == 0:
            self._draw_scene1(draw, local_t)
        elif scene_idx == 1:
            self._draw_scene2(draw, local_t)
        elif scene_idx == 2:
            self._draw_scene3(draw, local_t)
        else:
            self._draw_scene4(draw, local_t)

        self._draw_right_column(draw, scene, local_t)
        self._draw_bottom_bar(draw, global_t)
        return img


class RedFlagLoopHackathonRenderer(WidescreenHackathonRenderer):
    """1920x1080 30fps Widescreen Renderer for RedFlag-Loop (Sea × OpenAI Codex Hackathon)."""

    def __init__(
        self,
        *,
        font_loader: Optional[Callable[[List[str], int], Any]] = None,
    ) -> None:
        roadmap = [
            ("01 · ID-SCAMCHAT-72", "APK Resi · Phishing · QRIS · Escrow"),
            ("02 · AUTONOMOUS LOOP", "Write -> Run -> Evaluate -> Repair"),
            ("03 · GUARDRAIL & DIFF", "Candidate 2A Rollback · Whitelists"),
            ("04 · 1.000 F1 CONVERGED", "0.629 -> 1.000 F1 · 0 FP · 5/5 PASS"),
        ]
        super().__init__(
            scenes_spec=REDFLAG_SCENES_SPEC,
            caption_prefix="redflag",
            footer_project_tag="REDFLAG-LOOP · SEA × OPENAI CODEX",
            roadmap_items=roadmap,
            primary_accent=self.ACCENT_CYAN,
            font_loader=font_loader,
        )

    def _draw_scene1(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "INDONESIAN MARKETPLACE SCAM VECTORS vs BENIGN FALSE-POSITIVE TRAPS (ID-ScamChat-72)",
            font=self.font_panel_hdr,
            fill=self.ACCENT_ORANGE,
        )

        # 5 Adversarial Scam Vectors on Left
        scams = [
            ("V1 · FAKE COURIER .APK RESI", "\"Kak paket ditahan, buka file Cek_Resi_JNE_Express.apk ini ya\""),
            ("V2 · PHISHING CLAIM LINK", "\"Klik promo-undian-shopee-id.my.id/klaim untuk cairkan saldo\""),
            ("V3 · QRIS REFUND TRAP", "\"Scan barcode QRIS ini lalu masukkan PIN untuk terima refund\""),
            ("V4 · OFF-PLATFORM ESCROW BYPASS", "\"Chat WA 0812-xxxx langsung transfer BCA biar bebas biaya admin\""),
            ("V5 · FAKE CS URGENCY THREAT", "\"Akun diblokir 15 menit! Sebutkan kode OTP 6 digit sekarang\""),
        ]
        for idx, (v_title, v_chat) in enumerate(scams):
            sy0 = vy0 + 54 + idx * 84
            sy1 = sy0 + 72
            draw.rectangle([vx0 + 20, sy0, vx0 + 700, sy1], fill=(24, 19, 26), outline=self.ACCENT_RED, width=2)
            draw.rectangle([vx0 + 20, sy0, vx0 + 30, sy1], fill=self.ACCENT_RED)
            draw.text((vx0 + 42, sy0 + 10), v_title, font=self.font_mono_sm, fill=self.ACCENT_ORANGE)
            draw.text((vx0 + 42, sy0 + 38), v_chat, font=self.font_mono_xs, fill=self.INK_LIGHT)

        # Right Sub-Panel inside canvas: Gen 0 Baseline Failure (11 False Positives on Benign Chats)
        bx0, by0, bx1, by1 = vx0 + 720, vy0 + 54, vx1 - 20, vy0 + 462
        draw.rectangle([bx0, by0, bx1, by1], fill=(18, 24, 34), outline=self.ACCENT_AMBER, width=2)
        draw.rectangle([bx0, by0, bx1, by0 + 40], fill=(45, 32, 16))
        draw.text((bx0 + 14, by0 + 10), "GEN 0 BASELINE: 11 FALSE POSITIVES", font=self.font_mono_sm, fill=self.ACCENT_AMBER)

        fp_examples = [
            ("BENIGN #1 [FALSE POSITIVE]", "\"Nomor resi JNE asli: JP1928374650, cek di app\""),
            ("BENIGN #2 [FALSE POSITIVE]", "\"Silakan ajukan refund lewat Pusat Resolusi\""),
            ("BENIGN #3 [FALSE POSITIVE]", "\"Pembayaran QRIS resmi di halaman checkout\""),
            ("BENIGN #4 [FALSE POSITIVE]", "\"Link produk toko: tokopedia.com/toko/item\""),
        ]
        for idx, (fp_hdr, fp_txt) in enumerate(fp_examples):
            fy = by0 + 54 + idx * 84
            draw.rectangle([bx0 + 14, fy, bx1 - 14, fy + 70], fill=(24, 31, 44), outline=(65, 80, 102), width=1)
            draw.text((bx0 + 24, fy + 10), fp_hdr, font=self.font_mono_xs, fill=self.ACCENT_AMBER)
            draw.text((bx0 + 24, fy + 38), fp_txt, font=self.font_mono_xs, fill=self.INK_LIGHT)

        # Bottom Summary Strip
        draw.rectangle([vx0 + 20, vy0 + 480, vx1 - 20, vy1 - 18], fill=(18, 28, 40), outline=self.ACCENT_CYAN, width=2)
        draw.text(
            (vx0 + 36, vy0 + 496),
            "CHALLENGE: Eliminate 100% of False Positives on Legitimate Buyers/Sellers While Catching Obfuscated Scams",
            font=self.font_mono_sm,
            fill=self.ACCENT_CYAN,
        )
        draw.text(
            (vx0 + 36, vy0 + 532),
            "Gen 0 Baseline: Precision = 0.725 | Recall = 0.556 | F1 = 0.629 | 11 False Positives | 16 False Negatives",
            font=self.font_mono_xs,
            fill=self.INK_LIGHT,
        )

    def _draw_scene2(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "AUTONOMOUS CLOSED-LOOP AGENT: WRITE -> RUN -> EVALUATE -> REPAIR",
            font=self.font_panel_hdr,
            fill=self.ACCENT_CYAN,
        )

        # 4 Horizontal Pipeline Stage Nodes across top of canvas
        stages = [
            ("01 · WRITE", "Synthesize Rule AST", "Regex + Whitelist Guards"),
            ("02 · RUN", "Execute on 72 Chats", "36 Dev + 36 Holdout Val"),
            ("03 · EVALUATE", "Cluster FP & FN Slices", "Precision / Recall / F1"),
            ("04 · REPAIR", "Self-Correct Failure Modes", "Accept or Rollback Patch"),
        ]
        active_stage = int((local_t * 1.5) % 4)
        sw = (vx1 - vx0 - 76) // 4
        for idx, (s_title, s_sub, s_detail) in enumerate(stages):
            sx0 = vx0 + 20 + idx * (sw + 12)
            sy0 = vy0 + 56
            sx1 = sx0 + sw
            sy1 = sy0 + 132
            is_act = idx == active_stage
            bg_c = (20, 44, 58) if is_act else (18, 25, 36)
            bd_c = self.ACCENT_CYAN if is_act else (52, 66, 86)
            draw.rectangle([sx0, sy0, sx1, sy1], fill=bg_c, outline=bd_c, width=3 if is_act else 2)
            draw.text((sx0 + 16, sy0 + 14), s_title, font=self.font_mono_md, fill=self.ACCENT_CYAN if is_act else self.INK_LIGHT)
            draw.text((sx0 + 16, sy0 + 52), s_sub, font=self.font_mono_xs, fill=self.INK_LIGHT)
            draw.text((sx0 + 16, sy0 + 84), s_detail, font=self.font_mono_xs, fill=self.ACCENT_GREEN)

        # Bottom Left: Autonomous Error Clustering Matrix
        cx0, cy0, cx1, cy1 = vx0 + 20, vy0 + 210, vx0 + 590, vy1 - 20
        draw.rectangle([cx0, cy0, cx1, cy1], fill=(16, 22, 32), outline=(52, 68, 90), width=1)
        draw.text((cx0 + 16, cy0 + 14), "AUTONOMOUS FAILURE MODE CLUSTERING", font=self.font_mono_sm, fill=self.ACCENT_ORANGE)

        clusters = [
            ("CLUSTER FN-A (6 cases)", "Obfuscated '. a p k' & spaced WA digits -> Needs separator-tolerant regex"),
            ("CLUSTER FN-B (5 cases)", "Soft-urgency QRIS & fake CS refund links -> Needs compound intent rule"),
            ("CLUSTER FP-A (7 cases)", "Official courier resi (JNE/J&T/SiCepat) -> Needs safe context whitelist"),
            ("CLUSTER FP-B (4 cases)", "Legit 'Pusat Resolusi' refund discussion -> Needs escrow dispute guard"),
        ]
        for idx, (cl_id, cl_desc) in enumerate(clusters):
            ry = cy0 + 52 + idx * 78
            draw.rectangle([cx0 + 16, ry, cx1 - 16, ry + 64], fill=(22, 30, 44), outline=(46, 60, 80), width=1)
            draw.text((cx0 + 26, ry + 10), cl_id, font=self.font_mono_xs, fill=self.ACCENT_AMBER)
            draw.text((cx0 + 26, ry + 34), cl_desc, font=self.font_mono_xs, fill=self.INK_LIGHT)

        # Bottom Right: Live Agent Execution Telemetry Log
        lx0, ly0, lx1, ly1 = vx0 + 610, vy0 + 210, vx1 - 20, vy1 - 20
        draw.rectangle([lx0, ly0, lx1, ly1], fill=(10, 14, 20), outline=self.ACCENT_GREEN, width=1)
        draw.text((lx0 + 16, ly0 + 14), "SELF-EVOLUTION TRACE (ZERO HUMAN EDITS)", font=self.font_mono_sm, fill=self.ACCENT_GREEN)
        trace_lines = [
            ("[GEN 0 -> RUN]", "F1=0.629 | P=0.725 | R=0.556 | FP=11 | FN=16", self.INK_MUTED),
            ("[EVAL CLUSTER]", "Identified 4 dominant failure clusters on dev split", self.ACCENT_CYAN),
            ("[GEN 1 PATCH]", "Synthesized APK/link rules + basic courier guard", self.INK_LIGHT),
            ("[GEN 1 -> RUN]", "F1=0.824 | P=0.875 | R=0.778 | FP=4  | FN=8", self.ACCENT_GREEN),
            ("[NEXT TARGET]", "Eliminate remaining 4 FPs & 8 obfuscated FNs", self.ACCENT_AMBER),
        ]
        for idx, (t_tag, t_msg, t_col) in enumerate(trace_lines):
            ty = ly0 + 54 + idx * 64
            draw.text((lx0 + 16, ty), t_tag, font=self.font_mono_xs, fill=self.ACCENT_CYAN)
            draw.text((lx0 + 16, ty + 24), t_msg, font=self.font_mono_xs, fill=t_col)

    def _draw_scene3(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "PRECISION GUARDRAIL IN ACTION: CANDIDATE 2A ROLLBACK -> CANDIDATE 2B SYNTHESIS",
            font=self.font_panel_hdr,
            fill=self.ACCENT_AMBER,
        )

        # Top Half: Candidate 2A Overbroad Rule (REJECTED & ROLLED BACK)
        ax0, ay0, ax1, ay1 = vx0 + 20, vy0 + 54, vx1 - 20, vy0 + 286
        draw.rectangle([ax0, ay0, ax1, ay1], fill=(28, 16, 20), outline=self.ACCENT_RED, width=2)
        draw.rectangle([ax0, ay0, ax1, ay0 + 40], fill=(56, 20, 26))
        draw.text(
            (ax0 + 16, ay0 + 10),
            "CANDIDATE 2A (OVERBROAD REGEX) — PRECISION 0.895 < 1.00 GUARDRAIL -> AUTO-ROLLED BACK",
            font=self.font_mono_sm,
            fill=self.ACCENT_RED,
        )
        diff_bad = [
            "- RULE_2A: r\"(transfer|rekening|refund|qris|resi|klik|link)\"  # Overbroad token match!",
            "! FAILURE: Flagged benign buyer asking 'bagaimana cara refund di Pusat Resolusi?'",
            "! GUARDRAIL VERDICT: Precision dropped (2 new False Positives) -> REVERT COMMIT",
        ]
        for idx, line in enumerate(diff_bad):
            draw.text((ax0 + 20, ay0 + 56 + idx * 52), line, font=self.font_mono_sm, fill=self.INK_LIGHT)

        # Bottom Half: Repaired Candidate 2B + Gen 3 Whitelist & Obfuscation-Resilient Regex (ACCEPTED)
        bx0, by0, bx1, by1 = vx0 + 20, vy0 + 306, vx1 - 20, vy1 - 18
        draw.rectangle([bx0, by0, bx1, by1], fill=(14, 28, 24), outline=self.ACCENT_GREEN, width=2)
        draw.rectangle([bx0, by0, bx1, by0 + 40], fill=(18, 48, 38))
        draw.text(
            (bx0 + 16, by0 + 10),
            "CANDIDATE 2B / GEN 3 SELF-CORRECTION — PRECISION = 1.000 RESTORED (ACCEPTED)",
            font=self.font_mono_sm,
            fill=self.ACCENT_GREEN,
        )
        diff_good = [
            "+ SAFE_WHITELIST: r\"(pusat\\s+resolusi|klaim\\s+garansi\\s+resmi|resi\\s+(jne|j&t|sicepat)\\s+[A-Z0-9]{8,})\"",
            "+ APK_OBFUSCATION: r\"(cek[_\\s-]*resi|kurir|paket).*\\.[a\\s*p\\s*k|s\\s*c\\s*r]\"",
            "+ ESCROW_BYPASS: r\"(wa|whatsapp|tf|transfer\\s+langsung).*(08[0-9][\\s.-]*[0-9]{6,}|bebas\\s+admin)\"",
            "+ QRIS_REFUND_TRAP: r\"(scan\\s+qris|barcode\\s+refund).*(masukkan\\s+pin|cairkan\\s+dana)\"",
            "✓ VERIFIED: 0 False Positives on Benign Marketplace Chats · F1 = 0.936 (Gen 2B) -> 1.000 (Gen 3)",
        ]
        for idx, line in enumerate(diff_good):
            col = self.ACCENT_GREEN if idx == 4 else self.INK_LIGHT
            draw.text((bx0 + 20, by0 + 54 + idx * 44), line, font=self.font_mono_xs, fill=col)

    def _draw_scene4(self, draw: ImageDraw.ImageDraw, local_t: float) -> None:
        vx0, vy0, vx1, vy1 = 52, 220, 1230, 836
        draw.rectangle([vx0, vy0, vx1, vy1], fill=(12, 16, 22), outline=(60, 76, 100), width=2)

        draw.text(
            (vx0 + 22, vy0 + 16),
            "VERIFIED F1 CONVERGENCE TRAJECTORY (GEN 0 -> GEN 3) & ZERO FALSE POSITIVES",
            font=self.font_panel_hdr,
            fill=self.ACCENT_GREEN,
        )

        prog = self._ease_out_cubic(min(1.0, local_t / 1.8))

        # Left Sub-Panel: Generation Bar Chart (F1 & False Positive Elimination)
        cx0, cy0, cx1, cy1 = vx0 + 20, vy0 + 56, vx0 + 680, vy1 - 20
        draw.rectangle([cx0, cy0, cx1, cy1], fill=(16, 22, 32), outline=(52, 68, 90), width=1)
        draw.text((cx0 + 18, cy0 + 14), "F1 SCORE & FALSE POSITIVE CONVERGENCE", font=self.font_mono_sm, fill=self.ACCENT_CYAN)

        gens = [
            ("GEN 0 (Baseline)", 0.629, "11 FPs", self.ACCENT_AMBER),
            ("GEN 1 (Auto-Patch)", 0.824, "4 FPs", self.ACCENT_CYAN),
            ("GEN 2A (Rejected)", 0.861, "2 FPs [ROLLED BACK]", self.ACCENT_RED),
            ("GEN 2B (Guardrail)", 0.936, "0 FPs", self.ACCENT_GREEN),
            ("GEN 3 (Converged)", 1.000, "0 FPs · 0 FNs", self.ACCENT_ORANGE),
        ]
        max_bar_w = 360
        for idx, (g_name, g_f1, g_fp, g_col) in enumerate(gens):
            ry = cy0 + 58 + idx * 92
            draw.text((cx0 + 18, ry), f"{g_name}: F1 = {g_f1:.3f}  ({g_fp})", font=self.font_mono_sm, fill=self.INK_LIGHT)
            draw.rectangle([cx0 + 18, ry + 30, cx0 + 18 + max_bar_w, ry + 62], fill=(28, 36, 50))
            fill_w = int(max_bar_w * g_f1 * prog)
            draw.rectangle([cx0 + 18, ry + 30, cx0 + 18 + fill_w, ry + 62], fill=g_col)
            draw.text((cx0 + 392, ry + 34), f"{g_f1 * 100:.1f}%", font=self.font_mono_sm, fill=g_col)

        # Right Sub-Panel: Vellum Proof Card (Dev + Holdout Val Split & 5/5 Pytest)
        px0, py0, px1, py1 = vx0 + 700, vy0 + 56, vx1 - 20, vy1 - 20
        draw.rectangle([px0, py0, px1, py1], fill=self.BG_VELLUM, outline=self.INK_DARK, width=3)
        draw.rectangle([px0, py0, px1, py0 + 46], fill=self.ACCENT_ORANGE)
        draw.text((px0 + 16, py0 + 12), "SEA × OPENAI CODEX VERIFIED LEDGER", font=self.font_mono_sm, fill=self.INK_LIGHT)

        rows = [
            ("BENCHMARK:", "ID-ScamChat-72 (Indonesian)"),
            ("DEV SPLIT:", "36 Chats -> 1.000 F1 (0 FP)"),
            ("VAL SPLIT:", "36 Chats -> 1.000 F1 (0 FP)"),
            ("NET F1 GAIN:", "+0.371 (+37.1 pts vs Gen 0)"),
            ("GUARDRAIL:", "Candidate 2A Auto-Reverted"),
            ("PYTEST CI:", "5 / 5 PASSED (100% Green)"),
            ("HUMAN EDITS:", "0 (100% Autonomous Loop)"),
        ]
        for idx, (k, v) in enumerate(rows):
            ry = py0 + 66 + idx * 64
            draw.line([(px0 + 14, ry + 50), (px1 - 14, ry + 50)], fill=(210, 204, 192), width=1)
            draw.text((px0 + 16, ry + 10), k, font=self.font_mono_xs, fill=(71, 85, 105))
            draw.text((px0 + 152, ry + 10), v, font=self.font_mono_xs, fill=self.INK_DARK)

    def render_frame(self, frame_idx: int) -> Image.Image:
        if isinstance(frame_idx, bool) or not isinstance(frame_idx, int) or frame_idx < 0:
            raise ValueError(f"frame_idx must be a non-negative integer, got {frame_idx!r}")
        global_t = frame_idx / float(self.FPS)
        scene_idx = max(0, min(len(self.scenes_spec) - 1, int(global_t / 6.0)))
        scene = self.scenes_spec[scene_idx]
        local_t = max(0.0, global_t - scene["start_sec"])

        img = self.base_bg.copy()
        draw = ImageDraw.Draw(img)

        self._draw_chrome(draw, scene, local_t, global_t)
        if scene_idx == 0:
            self._draw_scene1(draw, local_t)
        elif scene_idx == 1:
            self._draw_scene2(draw, local_t)
        elif scene_idx == 2:
            self._draw_scene3(draw, local_t)
        else:
            self._draw_scene4(draw, local_t)

        self._draw_right_column(draw, scene, local_t)
        self._draw_bottom_bar(draw, global_t)
        return img


def _encode_widescreen_demo(
    renderer: WidescreenHackathonRenderer,
    output_dir: Union[str, Path],
    mp4_filename: str,
    title: str,
    hackathon_name: str,
    extra_metadata: Dict[str, Any],
    bpm: float = 120.0,
    *,
    total_frames_override: Optional[int] = None,
    soundtrack_fn: Callable[..., Any] = synthesize_showcase_soundtrack,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    which: Callable[[str], Optional[str]] = shutil.which,
    contact_sheet_fn: Callable[..., Path] = extract_contact_sheet,
    probe_fn: Callable[..., Any] = probe_media,
) -> Dict[str, Any]:
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    stem = Path(mp4_filename).stem
    mp4_path = out_path / mp4_filename
    srt_path = out_path / f"{stem}.srt"
    json_path = out_path / f"{stem}.json"
    wav_path = out_path / f"{stem}-soundtrack.wav"
    sheet_path = out_path / f"{stem}_sheet.png"

    fps = renderer.FPS
    total_frames = renderer.TOTAL_FRAMES if total_frames_override is None else int(total_frames_override)
    if total_frames < 1:
        raise ValueError(f"total_frames must be >= 1, got {total_frames!r}")
    duration_sec = renderer.DURATION_SEC if total_frames_override is None else round(total_frames / float(fps), 3)

    # 1. Synthesize 24.0s 48kHz stereo soundtrack
    soundtrack_manifest = soundtrack_fn(wav_path, duration_sec=duration_sec, bpm=bpm)

    # 2. Write companion .srt
    srt_lines: List[str] = []
    for idx, g in enumerate(renderer.caption_groups, start=1):
        s_str = _format_srt_time(g.start)
        e_str = _format_srt_time(g.end)
        srt_lines.append(f"{idx}\n{s_str} --> {e_str}\n{g.text}\n")
    srt_content = "\n".join(srt_lines).strip() + "\n"
    srt_path.write_text(srt_content, encoding="utf-8")

    # 3. Encode frames (1920x1080 RGB24) via FFmpeg pipe
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
        f"{renderer.WIDTH}x{renderer.HEIGHT}",
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

    proc = popen_factory(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.stdin is None:
        raise RuntimeError(f"FFmpeg launched without writable stdin pipe for {mp4_filename}")
    write_err: Optional[BaseException] = None
    try:
        for f_idx in range(total_frames):
            frame_img = renderer.render_frame(f_idx)
            proc.stdin.write(frame_img.tobytes())
    except (BrokenPipeError, OSError) as exc:
        write_err = exc
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass

    ret = proc.wait(timeout=180)
    if ret != 0 or write_err is not None:
        raise RuntimeError(
            f"FFmpeg encode failed for {mp4_filename} with exit code {ret}"
            + (f" ({write_err})" if write_err else "")
        )

    # 4. Extract 4x2 contact sheet & probe final media
    contact_sheet_fn(mp4_path, sheet_path, cols=4, rows=2)
    probe_res = probe_fn(mp4_path)

    # 5. Write companion JSON metadata
    metadata: Dict[str, Any] = {
        "title": title,
        "hackathon": hackathon_name,
        "author": "Ardhya Novri Ramadhan, S.T.",
        "portfolio_url": "https://ardhyanovri.my.id/",
        "repository_url": "https://github.com/vanovri",
        "output_video": str(mp4_path),
        "companion_srt": str(srt_path),
        "companion_json": str(json_path),
        "contact_sheet": str(sheet_path),
        "soundtrack_wav": str(wav_path),
        "spec": {
            "width": renderer.WIDTH,
            "height": renderer.HEIGHT,
            "aspect_ratio": "16:9",
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
            for s in renderer.scenes_spec
        ],
        "captions": [g.to_dict() for g in renderer.caption_groups],
        "verified_proof": extra_metadata,
    }
    json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def generate_benchmind_hackathon_demo(
    output_dir: Union[str, Path] = r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs",
    mp4_filename: str = "benchmind-v02-hackathon-demo-1920x1080.mp4",
    *,
    renderer: Optional[BenchMindHackathonRenderer] = None,
    total_frames_override: Optional[int] = None,
    soundtrack_fn: Callable[..., Any] = synthesize_showcase_soundtrack,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    which: Callable[[str], Optional[str]] = shutil.which,
    contact_sheet_fn: Callable[..., Path] = extract_contact_sheet,
    probe_fn: Callable[..., Any] = probe_media,
) -> Dict[str, Any]:
    """Render the 24.0s 1920x1080 30fps BenchMind v0.2.0 Meta Global AI Hackathon demo video."""
    active_renderer = renderer or BenchMindHackathonRenderer()
    extra = {
        "team_id": "1429535549246922",
        "version": "v0.2.0",
        "hardware": "STM32F411CEU6 + DFRobot SEN0240 EMG @ 4,000 Hz ADC+DMA",
        "pa0_dc_offset_mv": 150.25,
        "uart_frames_recovered": "1,997/1,997 (100%)",
        "uart_gain_over_naive": "+1,988 frames",
        "crc32_bit_flips_isolated": [17, 63, 142],
        "hum_50hz_attenuation_db": -25.5,
        "snr_improvement_db": 17.02,
        "hypotheses": ["RC-1", "RC-2", "RC-3", "RC-4"],
        "evidence_citations": ["E1", "E2", "E3", "E4", "E5", "E6", "F1", "F2", "F3", "F4", "F5"],
        "probe_actions": ["PA-1", "PA-2", "PA-3", "PA-4"],
        "sponsors": ["Meta Llama / Muse Spark", "Baseten", "Fireworks AI", "Modal"],
        "pytest_passed": "33/33",
    }
    return _encode_widescreen_demo(
        renderer=active_renderer,
        output_dir=output_dir,
        mp4_filename=mp4_filename,
        title="BenchMind v0.2.0 — AI Root-Cause Hardware Copilot & Signal Recovery",
        hackathon_name="Meta Global AI Developer Hackathon (Team ID 1429535549246922)",
        extra_metadata=extra,
        bpm=120.0,
        total_frames_override=total_frames_override,
        soundtrack_fn=soundtrack_fn,
        popen_factory=popen_factory,
        which=which,
        contact_sheet_fn=contact_sheet_fn,
        probe_fn=probe_fn,
    )


def generate_redflag_hackathon_demo(
    output_dir: Union[str, Path] = r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs",
    mp4_filename: str = "redflag-loop-sea-codex-demo-1920x1080.mp4",
    *,
    renderer: Optional[RedFlagLoopHackathonRenderer] = None,
    total_frames_override: Optional[int] = None,
    soundtrack_fn: Callable[..., Any] = synthesize_showcase_soundtrack,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    which: Callable[[str], Optional[str]] = shutil.which,
    contact_sheet_fn: Callable[..., Path] = extract_contact_sheet,
    probe_fn: Callable[..., Any] = probe_media,
) -> Dict[str, Any]:
    """Render the 24.0s 1920x1080 30fps RedFlag-Loop Sea × OpenAI Codex Hackathon demo video."""
    active_renderer = renderer or RedFlagLoopHackathonRenderer()
    extra = {
        "benchmark": "ID-ScamChat-72 (36 dev + 36 holdout val)",
        "scam_vectors": [
            "Fake Courier .apk Resi",
            "Phishing Links",
            "QRIS Refund Traps",
            "Off-Platform Escrow Bypass",
            "Fake CS Urgency",
        ],
        "loop_stages": ["Write", "Run", "Evaluate", "Repair"],
        "guardrail_rollback": "Candidate 2A rejected (Precision 0.895 < 1.00)",
        "f1_trajectory": {
            "gen_0": {"f1": 0.629, "false_positives": 11},
            "gen_1": {"f1": 0.824, "false_positives": 4},
            "gen_2a_rejected": {"f1": 0.861, "false_positives": 2, "status": "ROLLED_BACK"},
            "gen_2b": {"f1": 0.936, "false_positives": 0},
            "gen_3": {"f1": 1.000, "false_positives": 0, "false_negatives": 0},
        },
        "f1_gain": 0.371,
        "pytest_passed": "5/5",
    }
    return _encode_widescreen_demo(
        renderer=active_renderer,
        output_dir=output_dir,
        mp4_filename=mp4_filename,
        title="RedFlag-Loop — Self-Evolving Indonesian Marketplace Scam Detector",
        hackathon_name="Sea × OpenAI Codex Hackathon (Autonomous & Adaptive AI)",
        extra_metadata=extra,
        bpm=124.0,
        total_frames_override=total_frames_override,
        soundtrack_fn=soundtrack_fn,
        popen_factory=popen_factory,
        which=which,
        contact_sheet_fn=contact_sheet_fn,
        probe_fn=probe_fn,
    )


def generate_both_hackathon_demos(
    output_dir: Union[str, Path] = r"C:\Users\ardhy\Projects\agy-codex-video-studio\outputs",
    *,
    total_frames_override: Optional[int] = None,
    soundtrack_fn: Callable[..., Any] = synthesize_showcase_soundtrack,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    which: Callable[[str], Optional[str]] = shutil.which,
    contact_sheet_fn: Callable[..., Path] = extract_contact_sheet,
    probe_fn: Callable[..., Any] = probe_media,
) -> Dict[str, Dict[str, Any]]:
    """Render both 1920x1080 24.0s hackathon pitch videos and return their verification manifests."""
    bm_meta = generate_benchmind_hackathon_demo(
        output_dir=output_dir,
        total_frames_override=total_frames_override,
        soundtrack_fn=soundtrack_fn,
        popen_factory=popen_factory,
        which=which,
        contact_sheet_fn=contact_sheet_fn,
        probe_fn=probe_fn,
    )
    rf_meta = generate_redflag_hackathon_demo(
        output_dir=output_dir,
        total_frames_override=total_frames_override,
        soundtrack_fn=soundtrack_fn,
        popen_factory=popen_factory,
        which=which,
        contact_sheet_fn=contact_sheet_fn,
        probe_fn=probe_fn,
    )
    return {
        "benchmind": bm_meta,
        "redflag_loop": rf_meta,
    }
