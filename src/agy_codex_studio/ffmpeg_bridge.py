from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .contracts import MediaProbeResult

DEFAULT_SCRIPTS_DIR = Path(r"C:\Users\ardhy\repos\ffmpeg-skill\scripts")
_VALID_SCRIPT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _find_python(
    candidate: Optional[Union[str, Path]] = None,
    *,
    py314_path: Path = Path(r"C:\Python314\python.exe"),
) -> str:
    if candidate:
        return str(candidate)
    if py314_path.exists():
        return str(py314_path)
    return sys.executable


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_frame_rate(raw_rate: Any) -> float:
    if raw_rate is None or isinstance(raw_rate, bool):
        return 0.0
    text = str(raw_rate).strip()
    if not text or text.upper() == "N/A":
        return 0.0
    if "/" in text:
        parts = text.split("/", 1)
        num = _safe_float(parts[0], 0.0)
        den = _safe_float(parts[1], 0.0)
        if den <= 0.0:
            return 0.0
        val = num / den
        return val if math.isfinite(val) and val >= 0.0 else 0.0
    val = _safe_float(text, 0.0)
    return val if val >= 0.0 else 0.0


def _extract_embedded_json(stdout: str) -> Any:
    """Scan stdout for valid JSON object/array, ignoring inline bracketed log tags like '[1] booting'."""
    decoder = json.JSONDecoder()
    fallback: Any = None
    for idx, ch in enumerate(stdout):
        if ch in "{[":
            try:
                parsed, end_rel = decoder.raw_decode(stdout[idx:])
                if isinstance(parsed, (dict, list)):
                    rest_of_line = stdout[idx + end_rel :].split("\n", 1)[0].strip()
                    if rest_of_line == "":
                        return parsed
                    if fallback is None:
                        fallback = parsed
            except json.JSONDecodeError:
                continue
    return fallback


def _ensure_within_base_dir(script_path: Path, base_dir: Path, raw_name: str) -> None:
    if script_path.parent != base_dir:
        raise ValueError(f"Invalid script_name {raw_name!r}: path traversal blocked")


def run_ffmpeg_skill(
    script_name: str,
    args: Optional[List[str]] = None,
    scripts_dir: Optional[Union[str, Path]] = None,
    timeout: float = 60.0,
    *,
    runner: Callable[..., Any] = subprocess.run,
    python_exe: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a python script in ffmpeg-skill repo with --json flag and return parsed output."""
    if not isinstance(script_name, str) or not script_name.strip():
        raise ValueError(f"Invalid script_name: {script_name!r}")

    clean_name = script_name.strip().removesuffix(".py")
    if not _VALID_SCRIPT_NAME_RE.match(clean_name):
        raise ValueError(
            f"Invalid script_name {script_name!r}: only alphanumeric, underscore, and hyphen allowed"
        )

    base_dir = (Path(scripts_dir) if scripts_dir else DEFAULT_SCRIPTS_DIR).resolve()
    script_path = (base_dir / f"{clean_name}.py").resolve()
    _ensure_within_base_dir(script_path, base_dir, script_name)

    if not script_path.exists():
        raise FileNotFoundError(f"ffmpeg-skill script not found: {script_path}")

    call_args = [str(arg) for arg in (args or [])]
    if "--json" not in call_args and "-j" not in call_args:
        call_args.append("--json")

    cmd = [_find_python(python_exe), str(script_path)] + call_args
    proc = runner(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(base_dir),
    )

    stdout = (proc.stdout or "").strip()
    if not stdout and proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg-skill {script_name} failed with code {proc.returncode}: {proc.stderr}"
        )

    try:
        loaded = json.loads(stdout)
        if isinstance(loaded, dict):
            return loaded
        return {"status": "ok", "data": loaded}
    except json.JSONDecodeError:
        embedded = _extract_embedded_json(stdout)
        if embedded is not None:
            return embedded if isinstance(embedded, dict) else {"status": "ok", "data": embedded}
        return {
            "status": "raw",
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": proc.stderr,
        }


def probe_media(
    path: Union[str, Path],
    *,
    scripts_dir: Optional[Union[str, Path]] = None,
    runner: Callable[..., Any] = subprocess.run,
    which: Callable[[str], Optional[str]] = shutil.which,
) -> MediaProbeResult:
    """Inspect media file properties using probe.py from ffmpeg-skill with ffprobe fallback."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Media file not found: {p}")

    file_size = p.stat().st_size

    # 1. Try ffmpeg-skill probe.py
    try:
        res = run_ffmpeg_skill("probe", [str(p)], scripts_dir=scripts_dir, runner=runner)
        if isinstance(res, dict) and ("video" in res or "audio" in res or "duration" in res):
            v = res.get("video") or {}
            a = res.get("audio") or {}
            width = max(0, _safe_int(v.get("width"), 0))
            height = max(0, _safe_int(v.get("height"), 0))
            fps = max(0.0, _safe_float(v.get("fps"), 0.0))
            duration = max(0.0, _safe_float(res.get("duration"), 0.0))
            video_codec = str(v.get("codec") or "none")
            audio_codec = str(a.get("codec") or "none")
            has_audio = bool(a and a.get("codec"))
            return MediaProbeResult(
                file=str(p),
                width=width,
                height=height,
                fps=fps,
                duration_sec=duration,
                video_codec=video_codec,
                audio_codec=audio_codec,
                has_audio=has_audio,
                file_size_bytes=file_size,
                raw=res,
            )
    except Exception:
        pass

    # 2. Fallback to native ffprobe
    ffprobe_cmd = which("ffprobe") or "ffprobe"
    cmd = [
        ffprobe_cmd,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(p),
    ]
    try:
        proc = runner(cmd, capture_output=True, text=True)
    except Exception as exc:
        return MediaProbeResult(
            file=str(p),
            width=0,
            height=0,
            fps=0.0,
            duration_sec=0.0,
            video_codec="none",
            audio_codec="none",
            has_audio=False,
            file_size_bytes=file_size,
            raw={"error": f"probe failed: {exc}"},
        )

    if proc.returncode == 0 and (proc.stdout or "").strip():
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = None

        if isinstance(data, dict):
            streams = data.get("streams") if isinstance(data.get("streams"), list) else []
            fmt = data.get("format") if isinstance(data.get("format"), dict) else {}

            video_stream = next(
                (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"),
                None,
            )
            audio_stream = next(
                (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"),
                None,
            )

            width = max(0, _safe_int(video_stream.get("width"), 0)) if video_stream else 0
            height = max(0, _safe_int(video_stream.get("height"), 0)) if video_stream else 0
            fps = _parse_frame_rate(video_stream.get("r_frame_rate")) if video_stream else 0.0
            duration = max(0.0, _safe_float(fmt.get("duration"), 0.0))
            video_codec = str(video_stream.get("codec_name") or "none") if video_stream else "none"
            audio_codec = str(audio_stream.get("codec_name") or "none") if audio_stream else "none"
            has_audio = audio_stream is not None

            return MediaProbeResult(
                file=str(p),
                width=width,
                height=height,
                fps=fps,
                duration_sec=duration,
                video_codec=video_codec,
                audio_codec=audio_codec,
                has_audio=has_audio,
                file_size_bytes=file_size,
                raw=data,
            )

    return MediaProbeResult(
        file=str(p),
        width=0,
        height=0,
        fps=0.0,
        duration_sec=0.0,
        video_codec="none",
        audio_codec="none",
        has_audio=False,
        file_size_bytes=file_size,
        raw={"error": "probe failed"},
    )


def extract_contact_sheet(
    video_path: Union[str, Path],
    output_png: Union[str, Path],
    cols: int = 4,
    rows: int = 3,
    *,
    scripts_dir: Optional[Union[str, Path]] = None,
    runner: Callable[..., Any] = subprocess.run,
    which: Callable[[str], Optional[str]] = shutil.which,
) -> Path:
    """Generate a tiled contact sheet PNG from a video file."""
    if (
        isinstance(cols, bool)
        or isinstance(rows, bool)
        or not isinstance(cols, int)
        or not isinstance(rows, int)
        or cols < 1
        or rows < 1
    ):
        raise ValueError(f"cols and rows must be positive integers, got cols={cols!r}, rows={rows!r}")

    src = Path(video_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Video file not found: {src}")

    dst = Path(output_png).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)

    # 1. Try look.py from ffmpeg-skill
    try:
        run_ffmpeg_skill(
            "look",
            [str(src), "-o", str(dst), "--tiles", f"{cols}x{rows}"],
            scripts_dir=scripts_dir,
            runner=runner,
        )
        if dst.exists() and dst.stat().st_size > 0:
            return dst
    except Exception:
        pass

    # 2. Fallback to direct ffmpeg command
    ffmpeg_cmd = which("ffmpeg") or "ffmpeg"
    probe_res = probe_media(src, scripts_dir=scripts_dir, runner=runner, which=which)
    dur = probe_res.duration_sec if probe_res.duration_sec > 0 else 36.0
    num_tiles = cols * rows
    rate = max(0.1, num_tiles / dur)

    cmd = [
        ffmpeg_cmd,
        "-y",
        "-i",
        str(src),
        "-vf",
        f"fps={rate:.4f},scale=360:-1,tile={cols}x{rows}:padding=2:margin=2:color=0x202020",
        "-frames:v",
        "1",
        str(dst),
    ]
    runner(cmd, capture_output=True, check=True)
    return dst
