# AGY × Codex Video Studio (`v0.1.0`)

Multi-agent programmatic video production & motion graphics pipeline built collaboratively by **Antigravity (`agy`)** and **OpenAI Codex (`codex`)** via `agent-hub.py`, integrating the 10 open-source tools from `@haloziq` (`DfMxw43j2c8`).

---

## 1. Integrated Ecosystem (10 Tools / Repos)

| # | Tool / Repo | Local Path / Package | Role in AGY × Codex Video Studio |
|---|---|---|---|
| 1 | **Ghost Editor** (`kurbaitaev/ghost-editor`) | `C:\Users\ardhy\repos\ghost-editor` | Silence & filler trimmer (`ghost_trimmer.py`), repeated retake pruning, face-safe caption band |
| 2 | **FFmpeg Skill** (`kajisho5/ffmpeg-skill`) | `C:\Users\ardhy\repos\ffmpeg-skill` | 42 local FFmpeg/ffprobe tools + machine-readable contract (`ffmpeg_bridge.py`) |
| 3 | **Claude Shorts** (`AgriciDaniel/claude-shorts`) | `C:\Users\ardhy\repos\claude-shorts` | 5-dimension viral segment scorer (`shorts_scorer.py`) + natural cut boundary snapping |
| 4 | **MotionClone** (`blixvip/MotionClone`) | `C:\Users\ardhy\repos\MotionClone` | Reference motion reconstruction into editable HyperFrames HTML/GSAP + side-by-side comparison |
| 5 | **Motion Skills** (`iart-ai/motion-skills`) | `C:\Users\ardhy\repos\motion-skills` | Kinetic typography, animated data-viz (`chart-animation`), 9:16 retention & beat-sync soundtrack |
| 6 | **yt-dlp** (`yt-dlp/yt-dlp`) | `yt-dlp 2026.10.26` (`C:\Python314`) | Authorized media ingestion |
| 7 | **Faster-Whisper** (`SYSTRAN/faster-whisper`) | `faster-whisper 1.2.1` (`ctranslate2 4.8.5`, `av 19.0.2`) | Local word-level timestamp transcription |
| 8 | **Three.js Skills** (`CloudAI-X/threejs-skills`) | `C:\Users\ardhy\repos\threejs-skills` | Deterministic 3D frequency-response surface (`scene3.html`) driven by frame seek time |
| 9 | **HyperFrames** (`heygen-com/hyperframes`) | `hyperframes 0.8.206` | Deterministic frame-by-frame HTML/CSS/GSAP/Canvas to MP4 video renderer |
| 10 | **Agent Skills Hub** (`agentskillshub.top`) | Cross-agent skills synced | Installed across `.gemini/config/skills`, `.claude/skills`, `.codex/skills`, and `.hermes/skills` (0 excluded) |

---

## 2. True Multi-Agent Division of Labor (`agy` × `codex`)

- **OpenAI Codex (`codex`, Session `01a19dc8-ccee-7011-8ffe-7f5a4e2294d0`)**:
  - Built `src/agy_codex_studio/` (`contracts.py`, `ffmpeg_bridge.py`, `ghost_trimmer.py`, `caption_engine.py`, `shorts_scorer.py`, `soundtrack_synth.py`, `cli.py`).
  - Built and verified the unit test suite in `tests/test_studio_pipeline.py`.
  - Generated the 120 BPM stereo 48 kHz soundtrack (`studio/assets/soundtrack.wav`), word-timed captions (`captions.json`, `captions.srt`, `captions.vtt`), and `studio_manifest.json`.
- **Antigravity (`agy`, Conversation `8648920c-104f-45b1-abb5-2623abf6719b`)**:
  - Designed `studio/SPEC.md` and built the 5-scene vertical 1080×1920 30fps HyperFrames project (`studio/index.html`, `studio/compositions/scene1.html`–`scene5.html`, `studio/compositions/captions.html`).
  - Audited snapshots, fixed visual alignment, rendered the final 36.0s 1080×1920 MP4 showcase, and verified output via `ffprobe`, `npx hyperframes check --json`, and `ffmpeg-skill` `check.py`.

---

## 3. TDD Hardening, 100% Coverage & Mutation Verification (`v0.2.0`)

The repository includes a zero-dependency automated verification suite (`tests/unit/`, `tests/integration/`, `tests/adversarial/`) covering all 10 modules in `src/agy_codex_studio/`:

| Verification Layer | Suite / File | Result |
|---|---|---|
| **Line & Statement Coverage** | `pytest --cov=agy_codex_studio --cov-report=term-missing` | **100.00%** (`1,889 / 1,889` statements, `0` missed across `200` tests) |
| **Property-Based Differential Fuzzer** | `tests/adversarial/test_property_invariants_fuzzer.py` | **2,500 randomized cases** (`ghost_trimmer`, `caption_engine`, `shorts_scorer`, `soundtrack_synth`) |
| **AST Mutation Testing Harness** | `tests/adversarial/test_mutation_score.py` | **96.88% mutation kill score** (`62 / 64` in-memory AST mutants killed) |
| **Contract & SHA-256 Integrity Audit** | `tests/integration/test_contract_integrity_audit.py` | Verifies `SPEC_BACKEND_CONTRACT.md`, immutable `outputs/*.mp4` & `studio/` SHA-256 digests, and `p50/p95/p99` module latency |
| **Documented Bug Fixes** | [`BUGS_FIXED.md`](BUGS_FIXED.md) | **20 bugs** identified and fixed with regression tests |

---

## 4. Quick Commands

```powershell
# 1. Run full 200-test suite with 100% coverage report
$env:PYTHONPATH = "src"
C:\Python314\python.exe -m pytest --cov=agy_codex_studio --cov-report=term-missing -q

# 2. Generate showcase audio, captions, and manifest
C:\Python314\python.exe -m agy_codex_studio.cli generate-showcase-assets --out-dir studio/assets --duration 36.0

# 3. Validate and render 1080x1920 30fps MP4 via HyperFrames
Set-Location studio
npx hyperframes check --json
npx hyperframes render --quality delivery --output ..\outputs\signalproof-enviid-showcase-1080x1920.mp4
```
