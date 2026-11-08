# AGY Codex Video Studio technical debt

Crosschecked 2026-11-08 WIB. Locations are one-based against current source. Every patch is proposal-only, independently checked with git apply --check --recount and Python/TOML parsing. Production files and existing renders remain unchanged. No runtime speedup is claimed.

## 1. P1: Declare runtime dependencies and defer CLI renderer imports

Locations: `pyproject.toml:11`, `src/agy_codex_studio/__init__.py:32-36`, `src/agy_codex_studio/cli.py:20`, `src/agy_codex_studio/quad_showcase.py:10-11`, `src/agy_codex_studio/soundtrack_synth.py:7`.

The package declares dependencies=[] but requires NumPy for audio and quad rendering and Pillow for both Python renderer paths. Package initialization eagerly imports CLI, which imports the quad renderer. A clean installation can therefore fail to import even a lightweight submodule. The crosscheck runner first encountered missing PIL and supplied Pillow only in its isolated environment. That setup repair does not fix the repository manifest. The proposal declares the two direct runtime dependencies and lazily resolves the existing CLI facade exports. NumPy remains an eager package dependency. Pinning or bounds should follow the project's tested support policy rather than an invented version constraint.

```diff
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -8,7 +8,7 @@
 description = "AGY x Codex Video Studio — Multi-Agent Video & Motion Graphics Pipeline (FFmpeg Skill + Ghost Editor + Claude Shorts + MotionClone + HyperFrames)"
 readme = "README.md"
 requires-python = ">=3.11"
-dependencies = []
+dependencies = ["numpy", "Pillow"]
 
 [project.scripts]
 agy-codex-studio = "agy_codex_studio.cli:main"
diff --git a/src/agy_codex_studio/__init__.py b/src/agy_codex_studio/__init__.py
--- a/src/agy_codex_studio/__init__.py
+++ b/src/agy_codex_studio/__init__.py
@@ -28,11 +28,6 @@
     format_srt_document,
     format_vtt_document,
     sanitize_cue_text,
-)
-from .cli import (
-    build_parser,
-    inspect_environment,
-    run_cli,
 )
 from .shorts_scorer import (
     score_transcript_segments,
@@ -70,3 +65,12 @@
     "synthesize_showcase_soundtrack",
     "synthesize_soundtrack_pcm",
 ]
+
+
+def __getattr__(name: str):
+    if name in {"build_parser", "inspect_environment", "run_cli"}:
+        from . import cli
+        value = getattr(cli, name)
+        globals()[name] = value
+        return value
+    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

Validation: build and install the package into a clean temporary environment, verify NumPy/Pillow resolve, import contracts/caption helpers, then exercise the three public CLI facade names. Separately block PIL imports to confirm non-render package imports no longer depend on CLI loading. Preserve the console entry and public __all__ contract.

## 2. P2: Bound native tool fallbacks and doctor probes

Locations: `src/agy_codex_studio/ffmpeg_bridge.py:208`, `:336`; `src/agy_codex_studio/cli.py:87`, `:100`, `:113`, `:133`.

The ffmpeg-skill wrapper has a 60-second timeout, but native fallback calls and doctor version probes do not specify any timeout. A stalled process can block the caller indefinitely. The proposal gives the existing synchronous calls explicit budgets. Current exception handling records probe failure or doctor error, while a failed contact-sheet subprocess propagates to the caller. Calls are sequential, so these are per-process limits, not a single shared deadline. Popen frame writes in the separate encoders remain outside this patch's scope.

```diff
diff --git a/src/agy_codex_studio/ffmpeg_bridge.py b/src/agy_codex_studio/ffmpeg_bridge.py
--- a/src/agy_codex_studio/ffmpeg_bridge.py
+++ b/src/agy_codex_studio/ffmpeg_bridge.py
@@ -205,7 +205,7 @@
         str(p),
     ]
     try:
-        proc = runner(cmd, capture_output=True, text=True)
+        proc = runner(cmd, capture_output=True, text=True, timeout=60.0)
     except Exception as exc:
         return MediaProbeResult(
             file=str(p),
@@ -333,5 +333,5 @@
         "1",
         str(dst),
     ]
-    runner(cmd, capture_output=True, check=True)
+    runner(cmd, capture_output=True, check=True, timeout=60.0)
     return dst
diff --git a/src/agy_codex_studio/cli.py b/src/agy_codex_studio/cli.py
--- a/src/agy_codex_studio/cli.py
+++ b/src/agy_codex_studio/cli.py
@@ -84,7 +84,7 @@
     ff_bin = which("ffmpeg")
     if ff_bin:
         try:
-            p = runner([ff_bin, "-version"], capture_output=True, text=True, check=True)
+            p = runner([ff_bin, "-version"], capture_output=True, text=True, check=True, timeout=10.0)
             report["ffmpeg"] = {"status": "ok", "path": ff_bin, "version": _first_line(p.stdout)}
         except Exception as e:
             report["ffmpeg"] = {"status": "error", "error": str(e)}
@@ -97,7 +97,7 @@
     probe_bin = which("ffprobe")
     if probe_bin:
         try:
-            p = runner([probe_bin, "-version"], capture_output=True, text=True, check=True)
+            p = runner([probe_bin, "-version"], capture_output=True, text=True, check=True, timeout=10.0)
             report["ffprobe"] = {"status": "ok", "path": probe_bin, "version": _first_line(p.stdout)}
         except Exception as e:
             report["ffprobe"] = {"status": "error", "error": str(e)}
@@ -110,7 +110,7 @@
     ytdlp_bin = which("yt-dlp")
     if ytdlp_bin:
         try:
-            p = runner([ytdlp_bin, "--version"], capture_output=True, text=True, check=True)
+            p = runner([ytdlp_bin, "--version"], capture_output=True, text=True, check=True, timeout=10.0)
             report["yt_dlp"] = {"status": "ok", "path": ytdlp_bin, "version": (p.stdout or "").strip()}
         except Exception as e:
             report["yt_dlp"] = {"status": "error", "error": str(e)}
@@ -130,7 +130,7 @@
     if hf_direct or npx_bin:
         try:
             cmd = [hf_direct, "--version"] if hf_direct else [str(npx_bin), "hyperframes", "--version"]
-            p = runner(cmd, capture_output=True, text=True, shell=False)
+            p = runner(cmd, capture_output=True, text=True, shell=False, timeout=10.0)
             if p.returncode == 0:
                 report["hyperframes"] = {"status": "ok", "version": (p.stdout or "").strip()}
             else:
```

Validation: injected runners should assert timeout values and raise subprocess.TimeoutExpired. Verify probe failure metadata, doctor degraded status for required tools, and contact-sheet timeout propagation without launching encoders. A real timeout test should use a small inert child in a temporary directory and confirm no child survives. Version probes that invoke npx can still require external package availability.

## 3. P2: Make vertical render acceptance match its reported checks

Locations: `src/agy_codex_studio/cli.py:304-342` and `tests/unit/test_cli.py:92-142`.

verify-render catches a compliance-tool failure, writes that failure to JSON, and still returns 0 whenever dimensions and duration match. FPS, codecs and audio are also only reported. The existing test's compliance-error case simultaneously uses a wrong expected duration, so it does not isolate this permissive behavior. The stricter proposal accepts the local 1080x1920, 30 fps, H.264/AAC-with-audio contract only when check.py returns literal ok=True. The external local check.py confirms that boolean field is its JSON contract. This is an intentional compatibility change: unavailable compliance tooling now rejects acceptance, and 29.97 fps is outside the proposed 0.01 fps tolerance.

```diff
diff --git a/src/agy_codex_studio/cli.py b/src/agy_codex_studio/cli.py
--- a/src/agy_codex_studio/cli.py
+++ b/src/agy_codex_studio/cli.py
@@ -315,6 +315,11 @@
     dur_diff = abs(probe_result.duration_sec - expected_duration)
     is_duration_ok = dur_diff <= 0.5
     is_resolution_ok = probe_result.width == 1080 and probe_result.height == 1920
+    is_fps_ok = math.isfinite(probe_result.fps) and abs(probe_result.fps - 30.0) <= 0.01
+    is_audio_ok = probe_result.has_audio and probe_result.audio_codec == "aac"
+    is_video_codec_ok = probe_result.video_codec == "h264"
+    is_compliance_ok = compliance_check.get("ok") is True
+    accepted = all((is_duration_ok, is_resolution_ok, is_fps_ok, is_audio_ok, is_video_codec_ok, is_compliance_ok))
 
     verification_data = {
         "file": str(mp4_path),
@@ -324,6 +329,11 @@
         "duration_ok": is_duration_ok,
         "resolution": [probe_result.width, probe_result.height],
         "resolution_ok": is_resolution_ok,
+        "fps_ok": is_fps_ok,
+        "audio_ok": is_audio_ok,
+        "video_codec_ok": is_video_codec_ok,
+        "compliance_ok": is_compliance_ok,
+        "accepted": accepted,
         "fps": probe_result.fps,
         "video_codec": probe_result.video_codec,
         "audio_codec": probe_result.audio_codec,
@@ -339,7 +349,7 @@
         f"Duration: {probe_result.duration_sec:.2f}s (OK: {is_duration_ok}), "
         f"Resolution: {probe_result.width}x{probe_result.height} (OK: {is_resolution_ok})"
     )
-    return 0 if (is_duration_ok and is_resolution_ok) else 1
+    return 0 if accepted else 1
 
 
 def cmd_generate_quad_showcase(
```

Validation: hold dimensions/duration constant and independently inject compliance ok=False, compliance exceptions, absent/incorrect ok values, missing audio, wrong codecs, and wrong FPS. Each should produce accepted=False and exit1 under the proposal. Keep the all-valid case and duration mismatch case. A contact sheet and probe metadata do not establish visual quality or hardware truth.

## 4. P3: Avoid repeated suffix copies when scanning noisy JSON

Location: `src/agy_codex_studio/ffmpeg_bridge.py:67-88`.

Each opening bracket currently slices stdout[idx:] before JSONDecoder.raw_decode. Many invalid bracket candidates can copy progressively shorter suffixes, adding quadratic aggregate copying in the number of characters. Passing the original string plus a decoder offset removes those input copies. Reading only the remainder of the current line also avoids copying all later lines. JSON parsing itself can still revisit overlapping candidates, so this is not a proof that the full algorithm becomes linear. stdout capture remains unbounded in this proposal.

```diff
diff --git a/src/agy_codex_studio/ffmpeg_bridge.py b/src/agy_codex_studio/ffmpeg_bridge.py
--- a/src/agy_codex_studio/ffmpeg_bridge.py
+++ b/src/agy_codex_studio/ffmpeg_bridge.py
@@ -71,9 +71,10 @@
     for idx, ch in enumerate(stdout):
         if ch in "{[":
             try:
-                parsed, end_rel = decoder.raw_decode(stdout[idx:])
+                parsed, end = decoder.raw_decode(stdout, idx)
                 if isinstance(parsed, (dict, list)):
-                    rest_of_line = stdout[idx + end_rel :].split("\n", 1)[0].strip()
+                    line_end = stdout.find("\n", end)
+                    rest_of_line = stdout[end : line_end if line_end >= 0 else len(stdout)].strip()
                     if rest_of_line == "":
                         return parsed
                     if fallback is None:
```

Validation: preserve bracketed log-prefix handling, first valid object/list selection, same-line fallback behavior, trailing newlines and malformed candidate recovery. Compare allocation/time on large synthetic logs with many brackets before claiming a measurable benefit.
