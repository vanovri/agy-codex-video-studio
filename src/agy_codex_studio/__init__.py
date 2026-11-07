from __future__ import annotations

__version__ = "0.1.0"

from .contracts import (
    CaptionGroup,
    CutInterval,
    MediaProbeResult,
    ShortCandidate,
    SoundtrackManifest,
    TranscriptSegment,
    WordTimestamp,
)
from .ffmpeg_bridge import (
    DEFAULT_SCRIPTS_DIR,
    extract_contact_sheet,
    probe_media,
    run_ffmpeg_skill,
)
from .ghost_trimmer import (
    FILLER_WORDS,
    detect_and_trim_words,
)
from .caption_engine import (
    build_caption_groups,
    build_captions_payload,
    export_captions,
    format_srt_document,
    format_vtt_document,
    sanitize_cue_text,
)
from .cli import (
    build_parser,
    inspect_environment,
    run_cli,
)
from .shorts_scorer import (
    score_transcript_segments,
)
from .soundtrack_synth import (
    synthesize_showcase_soundtrack,
    synthesize_soundtrack_pcm,
)

__all__ = [
    "__version__",
    "CaptionGroup",
    "CutInterval",
    "MediaProbeResult",
    "ShortCandidate",
    "SoundtrackManifest",
    "TranscriptSegment",
    "WordTimestamp",
    "DEFAULT_SCRIPTS_DIR",
    "extract_contact_sheet",
    "probe_media",
    "run_ffmpeg_skill",
    "FILLER_WORDS",
    "detect_and_trim_words",
    "build_caption_groups",
    "build_captions_payload",
    "export_captions",
    "format_srt_document",
    "format_vtt_document",
    "sanitize_cue_text",
    "build_parser",
    "inspect_environment",
    "run_cli",
    "score_transcript_segments",
    "synthesize_showcase_soundtrack",
    "synthesize_soundtrack_pcm",
]
