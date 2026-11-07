from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Union
import wave
import numpy as np

from .contracts import SoundtrackManifest


def _validate_synth_params(duration_sec: float, bpm: float, sample_rate: int) -> tuple[float, float, int, int]:
    if (
        isinstance(duration_sec, bool)
        or not isinstance(duration_sec, (int, float))
        or not math.isfinite(duration_sec)
        or duration_sec <= 0.0
    ):
        raise ValueError(f"duration_sec must be a finite number > 0, got {duration_sec!r}")
    if (
        isinstance(bpm, bool)
        or not isinstance(bpm, (int, float))
        or not math.isfinite(bpm)
        or bpm <= 0.0
    ):
        raise ValueError(f"bpm must be a finite number > 0, got {bpm!r}")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError(f"sample_rate must be a positive integer, got {sample_rate!r}")

    n_samples = int(round(float(duration_sec) * sample_rate))
    if n_samples < 1:
        raise ValueError(
            f"duration_sec={duration_sec!r} at sample_rate={sample_rate} yields 0 samples"
        )
    return float(duration_sec), float(bpm), sample_rate, n_samples


def synthesize_soundtrack_pcm(
    duration_sec: float = 36.0,
    bpm: float = 120.0,
    sample_rate: int = 48000,
) -> Dict[str, Any]:
    """Pure in-memory stereo 16-bit PCM synthesizer (zero disk I/O)."""
    dur_val, bpm_val, sr, n_samples = _validate_synth_params(duration_sec, bpm, sample_rate)
    t = np.linspace(0.0, dur_val, n_samples, endpoint=False, dtype=np.float32)

    left = np.zeros(n_samples, dtype=np.float32)
    right = np.zeros(n_samples, dtype=np.float32)

    scenes = [
        (0.0, 5.0, 73.42, [146.83, 174.61, 220.00, 293.66], "Scene 1 (D Minor)"),
        (5.0, 12.0, 58.27, [116.54, 146.83, 174.61, 233.08], "Scene 2 (Bb Major)"),
        (12.0, 20.0, 87.31, [130.81, 174.61, 220.00, 261.63], "Scene 3 (F Major)"),
        (20.0, 28.5, 65.41, [130.81, 164.81, 196.00, 261.63], "Scene 4 (C Major)"),
        (29.0, 36.0, 73.42, [146.83, 174.61, 220.00, 293.66, 349.23], "Scene 5 (Dm Payoff)"),
    ]

    for t_start, t_end, root_hz, chord_hzs, _ in scenes:
        if t_start >= dur_val:
            continue
        actual_end = min(dur_val, t_end)
        mask = (t >= t_start) & (t < actual_end)
        idx = np.where(mask)[0]
        if len(idx) == 0:
            continue
        local_t = t[idx] - t_start
        dur = actual_end - t_start

        att_len = min(0.12, dur * 0.3)
        rel_len = min(0.20, dur * 0.3)
        env = np.ones(len(idx), dtype=np.float32)
        if att_len > 0:
            att_idx = local_t < att_len
            env[att_idx] = 0.5 * (1.0 - np.cos(np.pi * local_t[att_idx] / att_len))
        if rel_len > 0:
            rel_idx = local_t > (dur - rel_len)
            env[rel_idx] = 0.5 * (1.0 + np.cos(np.pi * (local_t[rel_idx] - (dur - rel_len)) / rel_len))

        if actual_end >= dur_val - 0.1 and dur > 1.2:
            fade_idx = local_t > (dur - 1.2)
            env[fade_idx] *= 0.5 * (1.0 + np.cos(np.pi * (local_t[fade_idx] - (dur - 1.2)) / 1.2))

        sub = 0.45 * np.sin(2.0 * np.pi * root_hz * local_t) + 0.12 * np.sin(4.0 * np.pi * root_hz * local_t)
        sub *= env
        left[idx] += sub * 0.70
        right[idx] += sub * 0.70

        for f_chord in chord_hzs:
            v_l = 0.08 * np.sin(2.0 * np.pi * (f_chord - 0.6) * local_t) + 0.04 * np.sin(4.0 * np.pi * f_chord * local_t)
            v_r = 0.08 * np.sin(2.0 * np.pi * (f_chord + 0.6) * local_t) + 0.04 * np.sin(4.0 * np.pi * f_chord * local_t)
            left[idx] += v_l * env
            right[idx] += v_r * env

    beat_sec = 60.0 / bpm_val
    total_beats = int(dur_val / beat_sec)
    beats: List[float] = [round(i * beat_sec, 3) for i in range(total_beats)]

    for b in beats:
        if 28.4 <= b <= 29.0:
            continue
        start_samp = int(b * sr)
        pulse_len = max(1, int(0.09 * sr))
        end_samp = min(n_samples, start_samp + pulse_len)
        if start_samp >= end_samp:
            continue
        dt = np.linspace(0.0, (end_samp - start_samp) / sr, end_samp - start_samp, endpoint=False, dtype=np.float32)
        freq = 45.0 + 75.0 * np.exp(-35.0 * dt)
        phase = 2.0 * np.pi * np.cumsum(freq) / sr
        kick = 0.22 * np.sin(phase) * np.exp(-22.0 * dt)
        left[start_samp:end_samp] += kick
        right[start_samp:end_samp] += kick

    text_entrances = [0.2, 2.4, 5.1, 8.5, 12.1, 16.0, 20.1, 24.4, 29.1, 32.6]
    for idx_ent, t_ent in enumerate(text_entrances):
        if t_ent >= dur_val:
            continue
        start_samp = int(t_ent * sr)
        tick_len = max(1, int(0.02 * sr))
        end_samp = min(n_samples, start_samp + tick_len)
        if start_samp >= end_samp:
            continue
        dt = np.linspace(0.0, (end_samp - start_samp) / sr, end_samp - start_samp, endpoint=False, dtype=np.float32)
        tick = 0.12 * np.sin(2.0 * np.pi * min(4200.0, sr * 0.4) * dt) * np.exp(-280.0 * dt)
        pan = 0.6 if idx_ent % 2 == 0 else 0.4
        left[start_samp:end_samp] += tick * pan
        right[start_samp:end_samp] += tick * (1.0 - pan)

    scene_cuts = [5.0, 12.0, 20.0]
    for cut_t in scene_cuts:
        if cut_t - 0.45 >= dur_val:
            continue
        w_start = max(0, int((cut_t - 0.45) * sr))
        w_end = min(n_samples, int((cut_t + 0.15) * sr))
        if w_start >= w_end:
            continue
        dt = np.linspace(0.0, (w_end - w_start) / sr, w_end - w_start, endpoint=False, dtype=np.float32)
        w_dur = (w_end - w_start) / sr
        env = np.sin(np.pi * dt / w_dur) ** 2
        f_sweep = 250.0 + 800.0 * (dt / w_dur)
        whoosh = 0.15 * np.sin(2.0 * np.pi * f_sweep * dt) * env
        pan_l = 1.0 - (dt / w_dur)
        pan_r = dt / w_dur
        left[w_start:w_end] += whoosh * pan_l
        right[w_start:w_end] += whoosh * pan_r

    if dur_val >= 25.0:
        r_start = int(24.5 * sr)
        r_end = min(n_samples, int(28.5 * sr))
        if r_start < r_end:
            dt_riser = np.linspace(0.0, (r_end - r_start) / sr, r_end - r_start, endpoint=False, dtype=np.float32)
            dur_riser = (r_end - r_start) / sr
            freq_riser = 180.0 + 720.0 * (dt_riser / dur_riser) ** 2
            phase_riser = 2.0 * np.pi * np.cumsum(freq_riser) / sr
            amp_riser = 0.04 + 0.22 * (dt_riser / dur_riser)
            riser = amp_riser * np.sin(phase_riser)
            left[r_start:r_end] += riser * 0.8
            right[r_start:r_end] += riser * 0.8

    if dur_val >= 28.6:
        silence_start = int(28.5 * sr)
        silence_end = min(n_samples, int(29.0 * sr))
        taper = max(1, int(0.005 * sr))
        if silence_start - taper >= 0:
            k_arr = np.arange(taper, dtype=np.float32)
            gains = 0.5 * (1.0 + np.cos(np.pi * k_arr / taper))
            left[silence_start - taper : silence_start] *= gains
            right[silence_start - taper : silence_start] *= gains
        left[silence_start:silence_end] = 0.0
        right[silence_start:silence_end] = 0.0

    if dur_val >= 29.1:
        payoff_start = int(29.0 * sr)
        payoff_len = max(1, int(1.2 * sr))
        payoff_end = min(n_samples, payoff_start + payoff_len)
        if payoff_start < payoff_end:
            dt_p = np.linspace(0.0, (payoff_end - payoff_start) / sr, payoff_end - payoff_start, endpoint=False, dtype=np.float32)
            chime = (
                0.18 * np.sin(2.0 * np.pi * 880.0 * dt_p)
                + 0.12 * np.sin(2.0 * np.pi * 1320.0 * dt_p)
                + 0.10 * np.sin(2.0 * np.pi * 1760.0 * dt_p)
            ) * np.exp(-3.5 * dt_p)
            left[payoff_start:payoff_end] += chime * 0.85
            right[payoff_start:payoff_end] += chime * 0.85

    max_peak_allowed = 0.835
    curr_peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))))
    curr_rms = float(np.sqrt(np.mean(0.5 * (left**2 + right**2))))

    target_rms = 0.190
    if curr_rms > 1e-6 and curr_peak > 1e-9:
        gain = target_rms / curr_rms
        if gain * curr_peak > max_peak_allowed:
            gain = max_peak_allowed / curr_peak
        left *= gain
        right *= gain

    left = np.tanh(left / max_peak_allowed) * max_peak_allowed
    right = np.tanh(right / max_peak_allowed) * max_peak_allowed

    final_peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))))
    final_rms = float(np.sqrt(np.mean(0.5 * (left**2 + right**2))))
    peak_dbfs = 20.0 * math.log10(max(final_peak, 1e-9))
    rms_dbfs = 20.0 * math.log10(max(final_rms, 1e-9))

    pcm_left = np.clip(left * 32767.0, -32767.0, 32767.0).astype(np.int16)
    pcm_right = np.clip(right * 32767.0, -32767.0, 32767.0).astype(np.int16)
    interleaved = np.empty((n_samples, 2), dtype=np.int16)
    interleaved[:, 0] = pcm_left
    interleaved[:, 1] = pcm_right

    scene_cues: Dict[str, Any] = {
        "scene_1": {"t_start": 0.0, "t_end": min(5.0, dur_val), "root": "D2", "key": "D minor", "label": "Hook: 50 Hz Hum Corrupts"},
        "scene_2": {"t_start": 5.0, "t_end": min(12.0, dur_val), "root": "Bb1", "key": "Bb major", "label": "Pipeline: STM32 4,000 Hz DMA"},
        "scene_3": {"t_start": 12.0, "t_end": min(20.0, dur_val), "root": "F2", "key": "F major", "label": "Biquad: -25.5 dB Notch Canyon"},
        "scene_4": {"t_start": 20.0, "t_end": min(28.5, dur_val), "root": "C2", "key": "C major", "label": "Data-Viz: Grip RMS Pearson r=0.9941"},
        "pre_payoff_break": {"t_start": 28.5, "t_end": min(29.0, dur_val), "label": "0.5s Pre-Payoff Silence Break"},
        "scene_5": {"t_start": 29.0, "t_end": dur_val, "root": "D2", "key": "D minor", "label": "Payoff: 12,043 Rows Zero Drops Ledger"},
    }

    return {
        "interleaved_pcm": interleaved,
        "duration_sec": dur_val,
        "sample_rate": sr,
        "channels": 2,
        "bpm": bpm_val,
        "beats": beats,
        "scene_cues": scene_cues,
        "peak_dbfs": round(peak_dbfs, 2),
        "rms_dbfs": round(rms_dbfs, 2),
    }


def synthesize_showcase_soundtrack(
    out_wav: Union[str, Path],
    duration_sec: float = 36.0,
    bpm: float = 120.0,
    sample_rate: int = 48000,
) -> SoundtrackManifest:
    """Deterministically synthesize a 48kHz 16-bit stereo electronic/technical soundtrack."""
    rendered = synthesize_soundtrack_pcm(
        duration_sec=duration_sec,
        bpm=bpm,
        sample_rate=sample_rate,
    )
    target_path = Path(out_wav).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(target_path), "wb") as wf:
        wf.setnchannels(rendered["channels"])
        wf.setsampwidth(2)
        wf.setframerate(rendered["sample_rate"])
        wf.writeframes(rendered["interleaved_pcm"].tobytes())

    return SoundtrackManifest(
        file=str(target_path),
        duration_sec=rendered["duration_sec"],
        sample_rate=rendered["sample_rate"],
        channels=rendered["channels"],
        bpm=rendered["bpm"],
        beats=rendered["beats"],
        scene_cues=rendered["scene_cues"],
        peak_dbfs=rendered["peak_dbfs"],
        rms_dbfs=rendered["rms_dbfs"],
    )
