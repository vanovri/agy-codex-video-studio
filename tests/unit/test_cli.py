from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List
import pytest

from agy_codex_studio.cli import (
    build_parser,
    cmd_doctor,
    cmd_generate_quad_showcase,
    cmd_generate_showcase_assets,
    cmd_verify_render,
    inspect_environment,
    run_cli,
)
from agy_codex_studio.contracts import MediaProbeResult


class FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_inspect_environment_marks_hyperframes_error_when_nonzero_exit() -> None:
    used_shell_flags: List[bool] = []

    def fake_which(tool: str) -> str | None:
        return f"/usr/bin/{tool}"

    def fake_runner(cmd: List[str], **kwargs: Any) -> FakeProc:
        used_shell_flags.append(bool(kwargs.get("shell", False)))
        if "hyperframes" in " ".join(cmd):
            return FakeProc(returncode=1, stdout="", stderr="npm ERR! not found")
        return FakeProc(returncode=0, stdout="tool version 1.0\n", stderr="")

    report = inspect_environment(
        which=fake_which,
        runner=fake_runner,
        skill_runner=lambda name, args: {"version": "1.0", "ok": True},
        whisper_checker=lambda: "1.2.1",
    )
    # Must NEVER use shell=True and MUST detect non-zero exit code on hyperframes!
    assert all(flag is False for flag in used_shell_flags)
    assert report["hyperframes"]["status"] == "error"
    assert report["ffmpeg"]["status"] == "ok"


def test_inspect_environment_degraded_when_core_tools_missing() -> None:
    report = inspect_environment(
        which=lambda _: None,
        runner=lambda *a, **kw: FakeProc(returncode=1),
        skill_runner=lambda *a: (_ for _ in ()).throw(FileNotFoundError("no skill")),
        whisper_checker=lambda: (_ for _ in ()).throw(ImportError("no whisper")),
    )
    assert report["all_ok"] is False
    assert report["ffmpeg"]["status"] == "missing"
    assert report["ffprobe"]["status"] == "missing"
    assert report["yt_dlp"]["status"] == "missing"
    assert report["faster_whisper"]["status"] == "missing"
    assert report["hyperframes"]["status"] == "missing"
    assert report["ffmpeg_skill"]["status"] == "error"


def test_cmd_doctor_human_readable_and_json_modes(capsys: pytest.CaptureFixture[str]) -> None:
    args_text = argparse.Namespace(json=False)
    code_degraded = cmd_doctor(
        args_text,
        which=lambda _: None,
        skill_runner=lambda *a: (_ for _ in ()).throw(RuntimeError("missing")),
    )
    out_text = capsys.readouterr().out
    assert code_degraded == 1
    assert "DEGRADED" in out_text

    args_json = argparse.Namespace(json=True)
    code_ok = cmd_doctor(
        args_json,
        which=lambda t: f"/bin/{t}",
        runner=lambda *a, **kw: FakeProc(0, "v1.0\n", ""),
        skill_runner=lambda *a: {"version": "1.0", "ok": True},
        whisper_checker=lambda: "1.2.1",
    )
    parsed = json.loads(capsys.readouterr().out)
    assert code_ok == 0
    assert parsed["all_ok"] is True


def test_cmd_verify_render_success_and_mismatch(tmp_path: Path) -> None:
    missing_args = argparse.Namespace(
        mp4_path=str(tmp_path / "missing.mp4"), expected_duration=36.0, out_dir=""
    )
    assert cmd_verify_render(missing_args) == 1

    mp4 = tmp_path / "reel.mp4"
    mp4.write_bytes(b"fake-mp4")

    def fake_probe(_p: Path) -> MediaProbeResult:
        return MediaProbeResult(
            file=str(mp4),
            width=1080,
            height=1920,
            fps=30.0,
            duration_sec=36.05,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            file_size_bytes=8,
        )

    def fake_sheet(_src: Path, dst: Path, cols: int = 4, rows: int = 3) -> Path:
        dst.write_bytes(b"png")
        return dst

    ok_args = argparse.Namespace(
        mp4_path=str(mp4), expected_duration=36.0, out_dir=str(tmp_path / "verify_out")
    )
    rc = cmd_verify_render(
        ok_args,
        probe_fn=fake_probe,
        skill_runner=lambda *a: {"ok": True, "platform": "reels"},
        contact_sheet_fn=fake_sheet,
    )
    assert rc == 0
    ver = json.loads((tmp_path / "verify_out" / "render_verification.json").read_text("utf-8"))
    assert ver["duration_ok"] is True
    assert ver["resolution_ok"] is True

    # Duration mismatch -> exit code 1
    bad_args = argparse.Namespace(
        mp4_path=str(mp4), expected_duration=24.0, out_dir=str(tmp_path / "verify_bad")
    )
    rc_bad = cmd_verify_render(
        bad_args,
        probe_fn=fake_probe,
        skill_runner=lambda *a: (_ for _ in ()).throw(RuntimeError("check err")),
        contact_sheet_fn=fake_sheet,
    )
    assert rc_bad == 1


def test_cmd_generate_showcase_assets_rejects_non_positive_duration(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        cmd_generate_showcase_assets(argparse.Namespace(out_dir=str(tmp_path), duration=0.0))


def test_run_cli_and_quad_subcommand_dispatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    parsed = parser.parse_args(["doctor", "--json"])
    assert parsed.subcommand == "doctor"

    fake_meta = {
        "output_video": str(tmp_path / "custom.mp4"),
        "companion_json": str(tmp_path / "custom.json"),
        "companion_srt": str(tmp_path / "custom.srt"),
        "probe_verification": {
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "video_codec": "h264",
            "audio_codec": "aac",
            "duration_sec": 24.0,
        },
    }
    rc = cmd_generate_quad_showcase(
        argparse.Namespace(out_dir=str(tmp_path)),
        generator_fn=lambda output_dir: fake_meta,
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "custom.json" in out

    rc_cli = run_cli(
        ["generate-showcase-assets", "--out-dir", str(tmp_path / "assets"), "--duration", "4.0"]
    )
    assert rc_cli == 0
    assert (tmp_path / "assets" / "studio_manifest.json").exists()
