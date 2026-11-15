# AGY x Codex Video Studio

A Python video-pipeline toolkit for transcript trimming, captions, segment scoring, PCM soundtrack synthesis, and FFmpeg command planning. The package manifest declares version 0.1.0.

## Implementation

- [Media contracts](src/agy_codex_studio/contracts.py).
- [Transcript trimming](src/agy_codex_studio/ghost_trimmer.py) and [captions](src/agy_codex_studio/caption_engine.py).
- [Segment scoring](src/agy_codex_studio/shorts_scorer.py) and [soundtrack synthesis](src/agy_codex_studio/soundtrack_synth.py).
- [FFmpeg integration](src/agy_codex_studio/ffmpeg_bridge.py) and [CLI](src/agy_codex_studio/cli.py).

## Run

Use Python 3.11 or later:

```sh
python -m pip install -e .
agy-codex-studio --help
```

NumPy and Pillow are Python runtime dependencies because the CLI imports the showcase renderer. Rendering and transcription also require external programs for the selected command. Installing this package does not install FFmpeg, HyperFrames, transcription models, or third-party skill repositories.

For repository checks:

```sh
python -m pip install -e ".[dev]"
python -m pip install graphifyy
graphify update . --no-cluster
python -m pytest -q
```

## Evidence and scope

Tests check pipeline contracts and included artifacts. The integration suite requires a generated Graphify graph with at least 150 nodes. Install Graphify separately and generate the index before running the suite. Without that index, its integrity assertion fails. Fixture tests do not verify every external integration or reproduce a coverage percentage, mutation score, or video render.

Showcase scripts contain prerecorded narration and synthetic examples. Their numerical narration is not a new EMG measurement or a verified ENVIID field result.

Developed with AI coding assistance. [Portfolio notes](https://ardhyanovri.my.id/projects/agy-codex-video-studio.html).
