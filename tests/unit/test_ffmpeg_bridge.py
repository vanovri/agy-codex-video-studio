from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, List
import pytest

from agy_codex_studio.ffmpeg_bridge import (
    extract_contact_sheet,
    probe_media,
    run_ffmpeg_skill,
)


class DummyCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_ffmpeg_skill_missing_script_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        run_ffmpeg_skill("nonexistent_tool", scripts_dir=tmp_path)


@pytest.mark.parametrize(
    "malicious_name",
    [
        "../../evil",
        "..\\..\\evil",
        "sub/evil",
        "sub\\evil",
        "",
        "   ",
    ],
)
def test_run_ffmpeg_skill_blocks_path_traversal_and_invalid_script_names(
    tmp_path: Path, malicious_name: str
) -> None:
    (tmp_path.parent / "evil.py").write_text("print('{}')", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="Invalid script_name"):
            run_ffmpeg_skill(malicious_name, scripts_dir=tmp_path)
    finally:
        (tmp_path.parent / "evil.py").unlink(missing_ok=True)


def test_run_ffmpeg_skill_parses_json_even_with_bracketed_log_prefix(tmp_path: Path) -> None:
    script = tmp_path / "probe.py"
    script.write_text("# stub", encoding="utf-8")

    captured_cmds: List[List[str]] = []

    def fake_runner(cmd: List[str], **kwargs: Any) -> DummyCompleted:
        captured_cmds.append(cmd)
        # Bracketed [INFO] prefix previously broke greedy r"(\{|\[).+(\}|\])" regex!
        noisy_stdout = '[INFO] Loading ffprobe...\n{"ok": true, "duration": 12.5}\n'
        return DummyCompleted(returncode=0, stdout=noisy_stdout, stderr="")

    res = run_ffmpeg_skill(
        "probe.py",
        args=["sample.mp4"],
        scripts_dir=tmp_path,
        runner=fake_runner,
        python_exe="python-stub",
    )
    assert res == {"ok": True, "duration": 12.5}
    assert "--json" in captured_cmds[0]


def test_run_ffmpeg_skill_raises_runtime_error_on_empty_nonzero_exit(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("# stub", encoding="utf-8")

    def fake_runner(cmd: List[str], **kwargs: Any) -> DummyCompleted:
        return DummyCompleted(returncode=2, stdout="", stderr="fatal codec error")

    with pytest.raises(RuntimeError, match="failed with code 2"):
        run_ffmpeg_skill("broken", scripts_dir=tmp_path, runner=fake_runner)


def test_run_ffmpeg_skill_returns_raw_dict_when_output_not_json(tmp_path: Path) -> None:
    (tmp_path / "plain.py").write_text("# stub", encoding="utf-8")

    def fake_runner(cmd: List[str], **kwargs: Any) -> DummyCompleted:
        return DummyCompleted(returncode=0, stdout="Plain text summary only", stderr="")

    res = run_ffmpeg_skill("plain", scripts_dir=tmp_path, runner=fake_runner)
    assert res["status"] == "raw"
    assert res["stdout"] == "Plain text summary only"


@pytest.mark.parametrize(
    ("r_frame_rate", "duration_str", "expected_fps", "expected_dur"),
    [
        ("30000/1001", "24.024", 29.97, 24.024),
        ("30/1", "36.0", 30.0, 36.0),
        ("0/0", "N/A", 0.0, 0.0),  # Corrupted / unknown container metadata!
        ("N/A", "", 0.0, 0.0),
        ("25", "10.5", 25.0, 10.5),
    ],
)
def test_probe_media_ffprobe_fallback_handles_edge_framerates_and_na(
    tmp_path: Path,
    r_frame_rate: str,
    duration_str: str,
    expected_fps: float,
    expected_dur: float,
) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"\x00" * 128)

    ffprobe_payload = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": r_frame_rate,
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": duration_str},
    }

    def fake_runner(cmd: List[str], **kwargs: Any) -> DummyCompleted:
        if any("probe.py" in str(c) for c in cmd):
            raise RuntimeError("skill unavailable")
        return DummyCompleted(returncode=0, stdout=json.dumps(ffprobe_payload))

    out = probe_media(media, runner=fake_runner, which=lambda name: name)
    assert out.width == 1920
    assert out.height == 1080
    assert out.fps == pytest.approx(expected_fps, abs=0.01)
    assert out.duration_sec == pytest.approx(expected_dur, abs=0.001)
    assert out.video_codec == "h264"
    assert out.audio_codec == "aac"
    assert out.has_audio is True


def test_probe_media_returns_safe_fallback_when_both_probes_fail(tmp_path: Path) -> None:
    media = tmp_path / "corrupt.mp4"
    media.write_bytes(b"corrupt")

    def fake_runner(cmd: List[str], **kwargs: Any) -> DummyCompleted:
        return DummyCompleted(returncode=1, stdout="", stderr="moov atom not found")

    res = probe_media(media, scripts_dir=tmp_path, runner=fake_runner)
    assert res.video_codec == "none"
    assert res.has_audio is False
    assert res.raw == {"error": "probe failed"}


def test_probe_media_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        probe_media(tmp_path / "missing.mp4")


def test_extract_contact_sheet_validates_inputs_and_uses_fallback(tmp_path: Path) -> None:
    missing = tmp_path / "nope.mp4"
    with pytest.raises(FileNotFoundError):
        extract_contact_sheet(missing, tmp_path / "out.png")

    vid = tmp_path / "vid.mp4"
    vid.write_bytes(b"video")
    with pytest.raises(ValueError, match="cols and rows"):
        extract_contact_sheet(vid, tmp_path / "out.png", cols=0, rows=3)

    out_png = tmp_path / "sheet.png"
    calls: List[List[str]] = []

    def fake_runner(cmd: List[str], **kwargs: Any) -> DummyCompleted:
        calls.append(cmd)
        if cmd[0] == "ffmpeg":
            out_png.write_bytes(b"\x89PNG\r\n\x1a\n")
            return DummyCompleted(returncode=0)
        return DummyCompleted(
            returncode=0,
            stdout=json.dumps({"format": {"duration": "12.0"}, "streams": []}),
        )

    result = extract_contact_sheet(
        vid,
        out_png,
        cols=4,
        rows=3,
        scripts_dir=tmp_path,  # no look.py -> triggers ffmpeg fallback
        runner=fake_runner,
        which=lambda b: b,
    )
    assert result == out_png.resolve()
    assert out_png.exists()
    assert any(c[0] == "ffmpeg" for c in calls)
