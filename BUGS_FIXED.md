# BUGS_FIXED.md — `agy-codex-video-studio`

Industrial TDD hardening (Phases 1–4) uncovered and fixed **20 real bugs and security/reliability vulnerabilities** across `src/agy_codex_studio/` while preserving 100% backward compatibility with all CLI commands, Python symbols, and `SPEC_BACKEND_CONTRACT.md` invariants.

---

## 1. Unrounded IEEE-754 Float Artifacts & `NaN`/`Inf` Serialization in Contracts
- **Location**: `src/agy_codex_studio/contracts.py` (`WordTimestamp`, `CaptionGroup`, `CutInterval`, `TranscriptSegment`, `ShortCandidate`, `MediaProbeResult`, `SoundtrackManifest`)
- **Root Cause**: `WordTimestamp.to_dict()` serialized raw `self.start`, `self.end`, and `self.score` without rounding (emitting `0.30000000000000004` on `0.1 + 0.2`), and none of the contract dataclasses rejected `NaN`, `±Inf`, boolean-as-int (`True`/`False`), or inverted intervals (`end < start`, negative dimensions/FPS).
- **Fix**: Added `_ensure_finite` and `_ensure_non_negative_int` validators across `__post_init__` hooks on all 7 dataclasses and rounded `WordTimestamp.to_dict()` fields (`start`/`end` to 3 decimals, `score` to 4 decimals).
- **Tests**: `tests/unit/test_contracts.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 2. Mutable Dictionary Aliasing in `.to_dict()` Serialization
- **Location**: `src/agy_codex_studio/contracts.py` (`CaptionGroup.safe_box`, `ShortCandidate.breakdown`, `MediaProbeResult.raw`, `SoundtrackManifest.scene_cues`)
- **Root Cause**: `.to_dict()` returned direct references to internal mutable dictionaries/lists; mutating the serialized payload silently corrupted the source dataclass instance.
- **Fix**: Used `copy.deepcopy(...)` on mutable dictionary/list fields inside `.to_dict()`.
- **Tests**: `tests/unit/test_contracts.py`

## 3. Invalid `max_words <= 0` / Negative `pause_break_sec` & Unreachable Dead Code in Caption Grouping
- **Location**: `src/agy_codex_studio/caption_engine.py` (`build_caption_groups`)
- **Root Cause**: Passing `max_words=0` or negative `max_words` fragmented every single token or broke chunk sizing without validation, negative `pause_break_sec` broke pause detection, and lines 79–90 contained unreachable dead code (`if gap_after >= pause_break_sec: pass`).
- **Fix**: Enforced `max_words >= 1` (rejecting `bool`), `pause_break_sec >= 0.0` (finite), stripped empty/whitespace-only words safely, and removed dead code.
- **Tests**: `tests/unit/test_caption_engine.py`

## 4. SRT / WebVTT Subtitle Cue Injection & Inverted Cue Timestamps
- **Location**: `src/agy_codex_studio/caption_engine.py` (`export_captions`, `sanitize_cue_text`, `format_srt_document`, `format_vtt_document`)
- **Root Cause**: `CaptionGroup.text` containing blank lines (`\n\n`) or timing arrows (`-->`) was interpolated verbatim into `.srt` and `.vtt` files, allowing untrusted ASR transcripts to inject arbitrary fake subtitle cues or corrupt WebVTT parsers. Additionally, `end < start` produced invalid negative-duration subtitle blocks.
- **Fix**: Extracted pure `sanitize_cue_text`, `build_captions_payload`, `format_srt_document`, and `format_vtt_document`; collapsed blank lines inside cues, neutralized `-->` (`->` in SRT, `--&gt;` in WebVTT), and clamped normalized cue bounds `end >= start >= 0.0`.
- **Tests**: `tests/unit/test_caption_engine.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 5. `NaN` / `Inf` Crash in `_format_srt_time` and `_format_vtt_time`
- **Location**: `src/agy_codex_studio/caption_engine.py` (`_format_srt_time`, `_format_vtt_time`)
- **Root Cause**: Non-finite floats raised opaque `OverflowError` / `ValueError` inside `round(sec * 1000)`.
- **Fix**: Validated finite numeric inputs upfront via `_require_finite`.
- **Tests**: `tests/unit/test_caption_engine.py`

## 6. Non-Monotonic / Overlapping Word Timestamps After Ghost Trimming
- **Location**: `src/agy_codex_studio/ghost_trimmer.py` (`detect_and_trim_words`)
- **Root Cause**: `remap_time` mapped `w.start` and `w.end` independently and enforced `max(0.05, new_end - new_start)`. Whenever an ASR filler cut overlapped the tail of a retained word or rapid `<50ms` words occurred back-to-back, `remapped[i].end > remapped[i + 1].start` occurred (timeline inversion).
- **Fix**: Added monotonic cursor clamping (`new_start = max(prev_end, raw_new_start)`) and sorted input words chronologically before cut detection.
- **Tests**: `tests/unit/test_ghost_trimmer.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 7. False-Positive Retake Deletion on Punctuation-Only Tokens
- **Location**: `src/agy_codex_studio/ghost_trimmer.py` (`detect_and_trim_words`)
- **Root Cause**: Two-word phrase retake matching checked `phrase_1 == phrase_2 and any(phrase_1)`. When a punctuation token (`"..."` -> `""`) preceded a repeated word (`"Signal"`), `("", "signal") == ("", "signal")` evaluated `True` and deleted legitimate non-retake speech.
- **Fix**: Changed guard to `all(phrase_1)` so both tokens in a 2-word retake prefix must contain non-empty lexical content, and validated non-negative finite `max_pause_sec`, `pad_start_sec`, and `pad_end_sec`.
- **Tests**: `tests/unit/test_ghost_trimmer.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 8. `target_max_sec` Completely Ignored Below `55.0s` in Viral Shorts Scorer
- **Location**: `src/agy_codex_studio/shorts_scorer.py` (`score_transcript_segments`)
- **Root Cause**: Window termination checked `if duration > max(55.0, target_max_sec): break`. Any caller passing `target_max_sec < 55.0` (including the function's own default `target_max_sec=45.0`!) still aggregated windows up to `55.0s`.
- **Fix**: Replaced hardcoded `max(55.0, target_max_sec)` with `duration > target_max_sec` (allowing single segments only up to `target_max_sec * 1.15` when `end_idx == start_idx`), and validated `0 < target_min_sec <= target_max_sec`.
- **Tests**: `tests/unit/test_shorts_scorer.py`

## 9. Unreachable Hyphenated Technical Terms (`crc-32`, `sha-256`) in Density Scorer
- **Location**: `src/agy_codex_studio/shorts_scorer.py` (`TECHNICAL_DOMAIN_TERMS`, `_score_density`)
- **Root Cause**: `_score_density` stripped all non-word characters via `re.sub(r"[^\w]", "", t)` (`"CRC-32"` -> `"crc32"`), making `"crc-32"` and `"sha-256"` in `TECHNICAL_DOMAIN_TERMS` 100% unreachable dead entries.
- **Fix**: Replaced hyphenated keys with normalized `"crc32"` and `"sha256"` matching the token normalizer.
- **Tests**: `tests/unit/test_shorts_scorer.py`

## 10. Broken `%` Word-Boundary Regex in Hook Scorer (`_score_hook`)
- **Location**: `src/agy_codex_studio/shorts_scorer.py` (`_score_hook`)
- **Root Cause**: Regex `\b(hz|...|%)\b` required a word boundary `\b` after `%`. Because `%` is `\W`, `"99.5% packet loss"` has `\W` followed by whitespace `\W` (no word boundary!), silently missing percentage hooks.
- **Fix**: Split `%` out of the `\b...\b` group into `(?:%|\b(?:hz|khz|...|x)\b)`.
- **Tests**: `tests/unit/test_shorts_scorer.py`

## 11. Quoted/Bracketed Sentences Penalized in Coherence Scorer (`_score_coherence`)
- **Location**: `src/agy_codex_studio/shorts_scorer.py` (`_score_coherence`)
- **Root Cause**: `clean[0].isupper()` and `clean[-1] in ".!?"` failed whenever a transcript started or ended with quotes/brackets (e.g., `'"STM32 captures 4000 Hz cleanly."'`).
- **Fix**: Stripped leading/trailing quote and bracket wrappers (`"'“”‘’()[]{}`) before evaluating capitalization and terminal punctuation.
- **Tests**: `tests/unit/test_shorts_scorer.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 12. `ZeroDivisionError` & Empty-Array Crash in Soundtrack Synthesizer
- **Location**: `src/agy_codex_studio/soundtrack_synth.py` (`synthesize_soundtrack_pcm`, `synthesize_showcase_soundtrack`)
- **Root Cause**: `bpm <= 0` raised `ZeroDivisionError` (`60.0 / bpm`), `duration_sec <= 0` raised `ValueError: zero-size array to reduction operation maximum`, and DSP synthesis was tightly coupled to WAV file writing.
- **Fix**: Extracted pure in-memory `synthesize_soundtrack_pcm` decoupled from WAV disk I/O and validated finite positive `duration_sec`, `bpm`, and `sample_rate`.
- **Tests**: `tests/unit/test_soundtrack_synth.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 13. Path Traversal Vulnerability in `run_ffmpeg_skill`
- **Location**: `src/agy_codex_studio/ffmpeg_bridge.py` (`run_ffmpeg_skill`)
- **Root Cause**: `scripts_dir / script_name` did not validate path separators or `..`, allowing `../../arbitrary_script` to execute Python files outside `DEFAULT_SCRIPTS_DIR`.
- **Fix**: Added `_resolve_safe_script_path` rejecting `/`, `\`, `..`, null bytes, and verifying `candidate.parent == base_dir`.
- **Tests**: `tests/unit/test_ffmpeg_bridge.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 14. Greedy Regex JSON Extraction Failure on Bracketed Log Prefixes
- **Location**: `src/agy_codex_studio/ffmpeg_bridge.py` (`run_ffmpeg_skill`, `_extract_json_payload`)
- **Root Cause**: When `json.loads(out)` failed due to leading log lines like `[INFO] starting\n{"ok": true}`, greedy regex `r"(\{|\[).+(\}|\])"` matched from `[INFO]` to `}`, feeding invalid JSON `[INFO] starting\n{"ok": true}` to `json.loads` and crashing.
- **Fix**: Replaced regex scraping with a `json.JSONDecoder.raw_decode` scanner that finds and parses valid JSON objects/arrays embedded after log prefixes.
- **Tests**: `tests/unit/test_ffmpeg_bridge.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 15. `ffprobe` `"N/A"` Float Crash & Unvalidated Contact-Sheet Grid Dimensions
- **Location**: `src/agy_codex_studio/ffmpeg_bridge.py` (`probe_media`, `extract_contact_sheet`)
- **Root Cause**: Containerless/corrupted streams cause `ffprobe` to emit `"duration": "N/A"` or `"r_frame_rate": "0/0"`, crashing `float("N/A")` with `ValueError`. `extract_contact_sheet` also accepted `cols <= 0` / `rows <= 0` and missing input files without clear errors.
- **Fix**: Added `_safe_float`, `_safe_int`, and `_parse_frame_rate` helpers plus upfront `cols >= 1`, `rows >= 1`, and `video_path.exists()` checks, along with full subprocess DI (`runner`, `which`).
- **Tests**: `tests/unit/test_ffmpeg_bridge.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 16. `shell=True` Execution, Unchecked `hyperframes` Exit Code, & Empty-Stdout `IndexError` in `cli.py:cmd_doctor`
- **Location**: `src/agy_codex_studio/cli.py` (`inspect_environment`, `cmd_doctor`)
- **Root Cause**: `cmd_doctor` ran `subprocess.run([hyperframes_bin, "--version"], shell=True)` and unconditionally set `"status": "ok"` even when `p.returncode != 0`, and indexed `p.stdout.splitlines()[0]` without guarding empty stdout (`IndexError`).
- **Fix**: Extracted pure `inspect_environment` with injectable `which`/`runner`, removed `shell=True`, verified `p.returncode == 0`, and added `_first_line` helper.
- **Tests**: `tests/unit/test_cli.py`

## 17. Fragile String `.replace` Metadata Path & Missing CLI Duration Validation
- **Location**: `src/agy_codex_studio/cli.py` (`cmd_generate_quad_showcase`, `cmd_generate_showcase_assets`, `cmd_verify_render`, `run_cli`)
- **Root Cause**: `cmd_generate_quad_showcase` derived JSON metadata path via `.replace('-1080x1920.mp4', '.json')` (breaking on custom filenames), `cmd_generate_showcase_assets` accepted negative durations, and `main()` could not accept an explicit `argv` list for isolated testing.
- **Fix**: Added `"companion_json"` directly to `generate_quad_showcase` metadata, validated duration bounds in `cli.py`, and exposed `build_parser()` and `run_cli(argv)`.
- **Tests**: `tests/unit/test_cli.py`, `tests/integration/test_pipeline_e2e.py`

## 18. Negative `frame_idx` Wrap-Around / `IndexError` in All Three Video Renderers
- **Location**: `src/agy_codex_studio/quad_showcase.py` (`QuadShowcaseRenderer.render_frame`) and `src/agy_codex_studio/hackathon_demos.py` (`BenchMindHackathonRenderer.render_frame`, `RedFlagLoopHackathonRenderer.render_frame`)
- **Root Cause**: `scene_idx = min(3, int(global_t / 6.0))` did not lower-clamp at `0` or reject negative `frame_idx`. Passing `-300` silently indexed `scenes_spec[-1]` with negative `local_t`, and `-900` crashed with `IndexError: list index out of range`.
- **Fix**: Validated `frame_idx` as a non-negative integer (`not isinstance(frame_idx, bool) and frame_idx >= 0`) and clamped `scene_idx` and `local_t >= 0.0`.
- **Tests**: `tests/unit/test_renderers.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 19. Unhandled `BrokenPipeError` & Tightly Coupled Subprocess/Font I/O in Video Generators
- **Location**: `src/agy_codex_studio/quad_showcase.py` (`generate_quad_showcase`, `_load_font`) and `src/agy_codex_studio/hackathon_demos.py` (`_encode_widescreen_demo`, `_load_font`)
- **Root Cause**: Writing raw RGB frames to `proc.stdin` crashed with raw `BrokenPipeError` if FFmpeg exited early, and hardcoded `C:\Windows\Fonts` / `subprocess.Popen` prevented deterministic unit/integration testing without spawning multi-minute x264 encodes.
- **Fix**: Added `fonts_dir` and `font_loader` DI to font loaders and renderers, added `soundtrack_fn`, `popen_factory`, `which`, `contact_sheet_fn`, `probe_fn` DI to generators, and caught `(BrokenPipeError, OSError)` cleanly with safe pipe teardown and descriptive `RuntimeError`.
- **Tests**: `tests/unit/test_renderers.py`, `tests/integration/test_pipeline_e2e.py`, `tests/adversarial/test_malicious_and_corrupted_inputs.py`

## 20. Whitespace-Only & Padded ASR `WordTimestamp` Tokens Corrupting Caption Grouping & Punctuation Breaks
- **Location**: `src/agy_codex_studio/caption_engine.py` (`build_caption_groups`) and `src/agy_codex_studio/ghost_trimmer.py` (`detect_and_trim_words`)
- **Root Cause**: Uncovered during Phase 3 AST mutation & property fuzzing: Whisper/ASR streams containing whitespace-only tokens (`WordTimestamp("  ", 0.0, 0.1)`) or trailing-space tokens (`WordTimestamp("locked. ", 0.1, 0.4)`) caused `build_caption_groups` to emit leading spaces (`"   Hello,"`), empty caption groups, and missed terminal punctuation breaks (`w.word.endswith(".")`). Additionally, `ghost_trimmer.py` contained an unreachable `j in retake_indices` inner-loop check.
- **Fix**: Normalized and filtered `cleaned_words` (`str(w.word).strip()`) after finite-timestamp validation in `build_caption_groups`, and removed the unreachable branch in `ghost_trimmer.py`.
- **Tests**: `tests/unit/test_caption_engine.py`, `tests/adversarial/test_mutation_score.py`, `tests/adversarial/test_property_invariants_fuzzer.py`

---

## Phase 2–4 Audit Metrics (`agy-codex-video-studio`)
- **Test Suite**: `200 / 200` passed (`0` failures, `0` warnings).
- **Code Coverage (`pytest --cov=agy_codex_studio`)**: **100.00% (`1,889` statements, `0` missed)** across all 10 modules (`__init__.py`, `caption_engine.py`, `cli.py`, `contracts.py`, `ffmpeg_bridge.py`, `ghost_trimmer.py`, `hackathon_demos.py`, `quad_showcase.py`, `shorts_scorer.py`, `soundtrack_synth.py`).
- **Property-Based Differential Fuzzer (`tests/adversarial/test_property_invariants_fuzzer.py`)**: **2,500 / 2,500** deterministic PRNG configurations passed (800 ASR word-timing/trim/caption monotonicity cases, 800 SRT/WebVTT adversarial cue round-trip cases, 600 viral-shorts scorer bound cases, 300 RIFF/WAVE PCM byte-alignment cases).
- **Zero-Dependency AST Mutation Harness (`tests/adversarial/test_mutation_score.py`)**: **62 / 64 AST mutants killed (96.88% kill score, >= 95% threshold)**.
- **Contract & Cryptographic SHA-256 Integrity (`tests/integration/test_contract_integrity_audit.py`)**: All 4 `outputs/*.mp4` files and `studio/` composition/asset digests verified 100% untouched; `p50/p95/p99` core latency benchmarks verified within budget.
