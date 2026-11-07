from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Dict, List

from PIL import ImageFont

from agy_codex_studio.caption_engine import (
    build_caption_groups,
    build_captions_payload,
    format_srt_document,
)
from agy_codex_studio.contracts import TranscriptSegment, WordTimestamp
from agy_codex_studio.ghost_trimmer import detect_and_trim_words
from agy_codex_studio.hackathon_demos import BenchMindHackathonRenderer
from agy_codex_studio.quad_showcase import QuadShowcaseRenderer, get_quad_showcase_words
from agy_codex_studio.shorts_scorer import score_transcript_segments
from agy_codex_studio.soundtrack_synth import synthesize_soundtrack_pcm

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_MP4_SHA256: Dict[str, str] = {
    "ardhya-engineering-quad-showcase-1080x1920.mp4": "d7655b42d7fc7dc5d9d6605c61d1b6380f9e082cf2f46ff316c5390ff4a24c4a",
    "benchmind-v02-hackathon-demo-1920x1080.mp4": "c2b641357970ceb34815e67ecdb4fb314d6777e2bbf18e6a70624fffcc4be1e3",
    "redflag-loop-sea-codex-demo-1920x1080.mp4": "6efbba3c9bd477c856952d6f1f2969c1321ebe8d8639ac2fbc3b23fc207b0deb",
    "signalproof-enviid-showcase-1080x1920.mp4": "3a18c18da951b8dda21a121bc514553ae0987b55d9e34ba6d7f192081627447e",
}

EXPECTED_STUDIO_COMPOSITIONS_SHA256: Dict[str, str] = {
    "studio/SPEC.md": "4467d053d2edb3070c41994e01ee6685f99c357b8b09cc65309aea78123545e0",
    "studio/REVIEW.md": "214d4afa5a64158d3d1b769d5855168abdb3702d6acab8a63cf640d8d4069423",
    "studio/index.html": "2c08b64df7a1cb2662bc698cc05f81b0d96a20d3650ab111b72c9feb357b9b21",
    "studio/compositions/captions.html": "071c644daeeccf219c5721823b2a5578a8d5a05d26e27a322c0f4774e195f0f4",
    "studio/compositions/scene1.html": "b8dac82ee2174b4415c3a3fe7ca18ffd9bd701fa0379fb1b21af549f073747ef",
    "studio/compositions/scene2.html": "bbe34a2b7e377a10ba29ae5ab8a43e2be4ba4eb48f035e7f4860bfe736583f65",
    "studio/compositions/scene3.html": "9eeec29140a0f8cb10fcacc720852b64b5e87143007694defeb9432affd5e66a",
    "studio/compositions/scene4.html": "c4d7a001f9165c0e153a34548fcefc9d940ea3f606ce03650db90a56459e4a16",
    "studio/compositions/scene5.html": "e50d0d9c23dd3316d345368bd693e23f74a75e5eabb3b25702a59438a85d8db6",
    "studio/assets/captions.json": "a758b207d1f8e7025c372fe1850d8d3a2fd01f9a7c2885741e2750d8f1e86ec5",
    "studio/assets/captions.srt": "9db2584ccd372ec86059d77cf3589ef6829e4e038d0d1aac517effb52bc5ee14",
    "studio/assets/captions.vtt": "dd819d2b0b4a440f68fc7a0fc27a8c2e40b815d0e2dd7095106317f860c05a04",
    "studio/assets/soundtrack.wav": "7e4759d7c9226af4fb300c6f62ad0ab8a01728b2670b497d15bb4fd37015794a",
    "studio/assets/studio_manifest.json": "21007a032dc57c8af19bd84ba75ddf8fa8588609d64d02c9af43718bef9fc15d",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile_ms(samples_ms: List[float], q: float) -> float:
    ordered = sorted(samples_ms)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def test_outputs_mp4_and_studio_sha256_digests_untouched() -> None:
    outputs_dir = REPO_ROOT / "outputs"
    for filename, expected_digest in EXPECTED_MP4_SHA256.items():
        mp4_path = outputs_dir / filename
        assert mp4_path.exists(), f"Missing rendered output video: {mp4_path}"
        assert _sha256(mp4_path) == expected_digest, f"SHA-256 mismatch on {filename}"

    for rel_path, expected_digest in EXPECTED_STUDIO_COMPOSITIONS_SHA256.items():
        target = REPO_ROOT / rel_path
        assert target.exists(), f"Missing studio file: {target}"
        assert _sha256(target) == expected_digest, f"SHA-256 modified in studio/: {rel_path}"


def test_spec_backend_contract_schema_and_graphify_index() -> None:
    spec_doc = (REPO_ROOT / "SPEC_BACKEND_CONTRACT.md").read_text(encoding="utf-8")
    assert "studio/" in spec_doc

    words = get_quad_showcase_words()
    groups = build_caption_groups(words, max_words=6, pause_break_sec=0.25)
    payload = build_captions_payload(groups)

    assert set(payload.keys()) == {"groups", "captions", "meta"}
    assert payload["meta"]["safe_box"] == {"x": 90, "y": 1180, "width": 900, "height": 150}
    assert all({"text", "startMs", "endMs"} <= set(c.keys()) for c in payload["captions"])

    graph_path = REPO_ROOT / "graphify-out" / "graph.json"
    assert graph_path.exists()
    graph_data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert len(graph_data.get("nodes", [])) >= 150


def test_core_modules_p50_p95_p99_latency_benchmarks() -> None:
    words = get_quad_showcase_words()
    groups = build_caption_groups(words)
    segments = [
        TranscriptSegment(id=g.id, text=g.text, start=g.start, end=g.end, words=g.words)
        for g in groups
    ]
    fast_loader = lambda _c, _s: ImageFont.load_default()
    quad_renderer = QuadShowcaseRenderer(font_loader=fast_loader)
    wide_renderer = BenchMindHackathonRenderer(font_loader=fast_loader)

    workloads = {
        "ghost_trimmer": (25, lambda: detect_and_trim_words(words)),
        "caption_engine": (25, lambda: format_srt_document(build_caption_groups(words))),
        "shorts_scorer": (25, lambda: score_transcript_segments(segments, 4.0, 20.0)),
        "soundtrack_pcm_1s": (15, lambda: synthesize_soundtrack_pcm(1.0, 120.0, 16000)),
        "quad_frame_render": (10, lambda: quad_renderer.render_frame(90)),
        "wide_frame_render": (10, lambda: wide_renderer.render_frame(90)),
    }

    metrics: Dict[str, Dict[str, float]] = {}
    for name, (iters, fn) in workloads.items():
        timings_ms: List[float] = []
        for _ in range(iters):
            t0 = time.perf_counter()
            fn()
            timings_ms.append((time.perf_counter() - t0) * 1000.0)
        p50 = _percentile_ms(timings_ms, 0.50)
        p95 = _percentile_ms(timings_ms, 0.95)
        p99 = _percentile_ms(timings_ms, 0.99)
        metrics[name] = {"p50_ms": round(p50, 3), "p95_ms": round(p95, 3), "p99_ms": round(p99, 3)}
        assert p50 <= p95 <= p99
        assert p99 < 2500.0, f"{name} p99 latency {p99:.2f}ms exceeded threshold"

    print(f"\n[Benchmark Audit p50/p95/p99 ms] {json.dumps(metrics)}")
    assert len(metrics) == 6
