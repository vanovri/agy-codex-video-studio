"""Exercise real verification/report logic with local, injected tool boundaries."""
from __future__ import annotations

import argparse
import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agy_codex_studio.cli import cmd_verify_render
from agy_codex_studio.ffmpeg_bridge import probe_media


def _verify(tmp_path: Path, compliance: dict[str, Any] | Exception, *, probe_fails: bool = False):
    media = tmp_path / "candidate.mp4"
    media.write_bytes(b"local-test-fixture")
    calls: list[list[str]] = []

    def ffprobe_runner(command: list[str], **kwargs: Any):
        calls.append(command)
        assert command[0] == "ffprobe-stub"
        assert command[-1] == str(media.resolve())
        assert "-show_streams" in command and "-show_format" in command
        if probe_fails:
            return SimpleNamespace(returncode=1, stdout="", stderr="invalid local media")
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps({
                "format": {"duration": "36.0"},
                "streams": [
                    {"codec_type": "video", "codec_name": "h264", "width": 1080,
                     "height": 1920, "r_frame_rate": "30/1"},
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
            }),
        )

    def check_runner(name: str, arguments: list[str]):
        assert name == "check"
        assert arguments == [str(media.resolve()), "--platform", "reels"]
        if isinstance(compliance, Exception):
            raise compliance
        return compliance

    def contact_sheet(source: Path, output: Path, *, cols: int, rows: int):
        assert source == media.resolve()
        assert (cols, rows) == (4, 3)
        output.write_bytes(b"contact-sheet-boundary-stub")
        return output

    output = tmp_path / "verification"
    code = cmd_verify_render(
        argparse.Namespace(mp4_path=str(media), expected_duration=36.0, out_dir=str(output)),
        probe_fn=partial(
            probe_media,
            scripts_dir=tmp_path / "absent-ffmpeg-skill",
            runner=ffprobe_runner,
            which=lambda _tool: "ffprobe-stub",
        ),
        skill_runner=check_runner,
        contact_sheet_fn=contact_sheet,
    )
    report = json.loads((output / "render_verification.json").read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert report["contact_sheet"] == str(output / "candidate_sheet.png")
    return code, report


def test_verified_dimensions_and_successful_compliance_write_complete_report(tmp_path: Path):
    code, report = _verify(tmp_path, {"ok": True, "platform": "reels"})
    assert code == 0
    assert report["duration_ok"] is True
    assert report["resolution_ok"] is True
    assert report["fps"] == 30.0
    assert report["video_codec"] == "h264"
    assert report["audio_codec"] == "aac"
    assert report["compliance_check"]["ok"] is True


def test_failed_native_probe_rejects_even_when_compliance_says_ok(tmp_path: Path):
    code, report = _verify(tmp_path, {"ok": True}, probe_fails=True)
    assert code == 1
    assert report["duration_ok"] is False
    assert report["resolution_ok"] is False
    assert report["resolution"] == [0, 0]
    assert report["video_codec"] == "none"


@pytest.mark.parametrize(
    "compliance",
    [{"ok": False}, {}, {"ok": "true"}, RuntimeError("compliance tool unavailable")],
    ids=["explicit-failure", "missing-ok", "non-boolean-ok", "tool-exception"],
)
def test_compliance_must_independently_gate_acceptance(tmp_path: Path, compliance):
    code, report = _verify(tmp_path, compliance)
    assert report["duration_ok"] is True
    assert report["resolution_ok"] is True
    assert report["compliance_check"].get("ok") is not True
    assert code == 1
