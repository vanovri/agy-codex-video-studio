# AGY × Codex Video Studio — Backend & CLI Contract (Owned by OpenAI Codex)

## Role Split
- **Codex (`codex`)**: Owns `src/agy_codex_studio/` and `tests/`. Do NOT modify `studio/` (owned by Antigravity `agy`).
- **Antigravity (`agy`)**: Owns `studio/` (HyperFrames 1080×1920 30fps compositions, Three.js WebGL 3D scene, kinetic typography, animated data-viz, and final render/inspection).

## Modules Required in `src/agy_codex_studio/`

1. **`contracts.py`**:
   - Dataclasses (`WordTimestamp`, `TranscriptSegment`, `CaptionGroup`, `CutInterval`, `ShortCandidate`, `MediaProbeResult`, `SoundtrackManifest`) with `.to_dict()`.

2. **`ffmpeg_bridge.py`**:
   - Wrapper for `C:\Users\ardhy\repos\ffmpeg-skill\scripts\` (`_contract.py`, `probe.py`, `silence.py`, `cut.py`, `fit.py`, `loudness.py`, `check.py`, `look.py`) + fallback `ffprobe`/`ffmpeg` subprocess helpers.
   - `run_ffmpeg_skill(script_name: str, args: list[str]) -> dict`: invokes `C:\Python314\python.exe C:\Users\ardhy\repos\ffmpeg-skill\scripts\<script_name>.py ... --json`.
   - `probe_media(path: str | Path) -> MediaProbeResult`: returns width, height, fps, duration_sec, video_codec, audio_codec, has_audio, file_size_bytes.
   - `extract_contact_sheet(video_path: str | Path, output_png: str | Path, cols: int = 4, rows: int = 3) -> Path`: creates tiled contact sheet PNG via `ffmpeg`.

3. **`ghost_trimmer.py`** (inspired by `kurbaitaev/ghost-editor`):
   - `FILLER_WORDS = {"um", "uh", "er", "ah", "hmm", "uhm", "erm", "anu", "eee", "eh"}`
   - `detect_and_trim_words(words: list[WordTimestamp], max_pause_sec: float = 0.35, pad_start_sec: float = 0.08, pad_end_sec: float = 0.12) -> dict`:
     - Removes standalone filler words and compresses inter-word silences > `max_pause_sec`.
     - Detects repeated retakes (when a sentence prefix is repeated within 8 seconds, keeps the later fluent take).
     - Returns `{"kept_words": [...], "cut_intervals": [...], "removed_fillers": int, "saved_seconds": float, "remapped_words": [...]}`.

4. **`caption_engine.py`** (inspired by `ghost-editor` + `AgriciDaniel/claude-shorts` + `hyperframes/references/captions.md`):
   - `build_caption_groups(words: list[WordTimestamp], max_words: int = 4, pause_break_sec: float = 0.22) -> list[CaptionGroup]`:
     - Groups word timestamps into 2–5 word phrases, breaking on punctuation (`.`, `,`, `!`, `?`, `—`, `:`) or pauses >= `pause_break_sec`.
     - Assigns safe 9:16 portrait layout metadata (`safe_box={"x": 90, "y": 1180, "width": 900, "height": 150}`).
   - `export_captions(groups: list[CaptionGroup], out_dir: str | Path) -> dict`:
     - Writes `captions.json` (both HyperFrames `groups` + Remotion `captions` `{text, startMs, endMs}`), `captions.srt`, and `captions.vtt`.

5. **`shorts_scorer.py`** (inspired by `AgriciDaniel/claude-shorts`):
   - Scores candidate segments (`15.0` to `55.0` sec) across 5 weighted dimensions:
     - `hook_strength` (weight `0.30`): numbers, technical claims, pattern-interrupt keywords, strong opening.
     - `standalone_coherence` (weight `0.25`): starts at sentence boundary, ends on terminal punctuation, no dangling pronouns.
     - `emotional_intensity` (weight `0.20`): contrast words, high-impact verbs, verification proof.
     - `information_density` (weight `0.15`): unique domain terms per second, concrete metrics.
     - `natural_boundaries` (weight `0.10`): clean pause before/after cut point (`snap_to_silence`).
   - `score_transcript_segments(segments: list[TranscriptSegment], target_min_sec: float = 15.0, target_max_sec: float = 45.0) -> list[ShortCandidate]`: returns sorted candidates with weighted total score (`0.0` to `10.0`) and breakdown.

6. **`soundtrack_synth.py`** (inspired by `iart-ai/motion-skills` `soundtrack` + `hyperframes/references/sound.md`):
   - Pure Python (`wave`, `math`, `struct` / `numpy`) deterministic stereo 48 kHz 16-bit WAV generator:
     - `synthesize_showcase_soundtrack(out_wav: str | Path, duration_sec: float = 36.0, bpm: float = 120.0) -> SoundtrackManifest`:
     - Generates a 120 BPM (`0.5s` per beat) procedural electronic/technical score with:
       - Warm sub-bass + harmonic pad progression (`D minor -> Bb major -> F major -> C major`, walking to tonic on scene cuts at `t = 0.0, 5.0, 12.0, 20.0, 29.0, 36.0`)
       - Subtle pulse percussion, soft key-ticks on kinetic text entrances, whoosh transitions at scene cuts (`5.0s`, `12.0s`, `20.0s`, `29.0s`), and a riser into the `29.0s` payoff (with a 0.5s pre-payoff silence break at `28.5s–29.0s` per `soundtrack/SKILL.md`!).
       - True peak capped below `-1.5 dBFS` and RMS calibrated to social loudness (`~ -14 LUFS`).
       - Writes `soundtrack.wav` and returns beat grid + cue timestamps.

7. **`cli.py`**:
   - Subcommands:
     - `doctor`: checks `ffmpeg`, `ffprobe`, `yt-dlp`, `faster_whisper`, `hyperframes`, and `ffmpeg-skill` contract.
     - `generate-showcase-assets --out-dir <dir> --duration 36.0`: generates:
       - `soundtrack.wav` (36.0s 48kHz stereo WAV)
       - `captions.json`, `captions.srt`, `captions.vtt` (word-timed technical narration captions for the 36s SignalProof Lab × ENVIID showcase across all 5 scenes)
       - `studio_manifest.json` (complete beat grid, scene cut cues, trimmed transcript stats, short segment score report, and verified thesis/ENVIID data metrics)
     - `verify-render <mp4_path> --expected-duration 36.0`: runs `ffprobe` + `ffmpeg-skill` `probe.py` & `check.py`, extracts a `4x3` contact sheet PNG, and writes `render_verification.json`.

8. **`tests/test_studio_pipeline.py`**:
   - Comprehensive `pytest` suite (at least 12 tests) covering all modules + CLI asset generation.
