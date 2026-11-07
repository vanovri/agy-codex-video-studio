from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Union


def _finite_round(value: Union[int, float], ndigits: int, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number, got {value!r}")
    return round(float(value), ndigits)


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "start": _finite_round(self.start, 3, "WordTimestamp.start"),
            "end": _finite_round(self.end, 3, "WordTimestamp.end"),
            "score": _finite_round(self.score, 3, "WordTimestamp.score"),
        }


@dataclass
class TranscriptSegment:
    id: Union[int, str]
    text: str
    start: float
    end: float
    words: List[WordTimestamp] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "start": _finite_round(self.start, 3, "TranscriptSegment.start"),
            "end": _finite_round(self.end, 3, "TranscriptSegment.end"),
            "words": [w.to_dict() for w in self.words],
        }


@dataclass
class CaptionGroup:
    id: str
    text: str
    start: float
    end: float
    words: List[WordTimestamp] = field(default_factory=list)
    safe_box: Dict[str, Any] = field(
        default_factory=lambda: {"x": 90, "y": 1180, "width": 900, "height": 150}
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "start": _finite_round(self.start, 3, "CaptionGroup.start"),
            "end": _finite_round(self.end, 3, "CaptionGroup.end"),
            "words": [w.to_dict() for w in self.words],
            "safe_box": copy.deepcopy(self.safe_box),
        }


@dataclass
class CutInterval:
    start: float
    end: float
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        s = _finite_round(self.start, 3, "CutInterval.start")
        e = _finite_round(self.end, 3, "CutInterval.end")
        dur = max(0.0, float(self.end) - float(self.start))
        return {
            "start": s,
            "end": e,
            "duration": _finite_round(dur, 3, "CutInterval.duration"),
            "reason": self.reason,
        }


@dataclass
class ShortCandidate:
    start: float
    end: float
    score: float
    hook_strength: float
    standalone_coherence: float
    emotional_intensity: float
    information_density: float
    natural_boundaries: float
    text: str
    breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        s = _finite_round(self.start, 3, "ShortCandidate.start")
        e = _finite_round(self.end, 3, "ShortCandidate.end")
        dur = max(0.0, float(self.end) - float(self.start))
        return {
            "start": s,
            "end": e,
            "duration": _finite_round(dur, 3, "ShortCandidate.duration"),
            "score": _finite_round(self.score, 2, "ShortCandidate.score"),
            "hook_strength": _finite_round(self.hook_strength, 2, "ShortCandidate.hook_strength"),
            "standalone_coherence": _finite_round(
                self.standalone_coherence, 2, "ShortCandidate.standalone_coherence"
            ),
            "emotional_intensity": _finite_round(
                self.emotional_intensity, 2, "ShortCandidate.emotional_intensity"
            ),
            "information_density": _finite_round(
                self.information_density, 2, "ShortCandidate.information_density"
            ),
            "natural_boundaries": _finite_round(
                self.natural_boundaries, 2, "ShortCandidate.natural_boundaries"
            ),
            "text": self.text,
            "breakdown": copy.deepcopy(self.breakdown),
        }


@dataclass
class MediaProbeResult:
    file: str
    width: int
    height: int
    fps: float
    duration_sec: float
    video_codec: str
    audio_codec: str
    has_audio: bool
    file_size_bytes: int
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "width": self.width,
            "height": self.height,
            "fps": _finite_round(self.fps, 3, "MediaProbeResult.fps"),
            "duration_sec": _finite_round(self.duration_sec, 3, "MediaProbeResult.duration_sec"),
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "has_audio": self.has_audio,
            "file_size_bytes": self.file_size_bytes,
            "raw": copy.deepcopy(self.raw),
        }


@dataclass
class SoundtrackManifest:
    file: str
    duration_sec: float
    sample_rate: int
    channels: int
    bpm: float
    beats: List[float]
    scene_cues: Dict[str, Any]
    peak_dbfs: float
    rms_dbfs: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "duration_sec": _finite_round(self.duration_sec, 3, "SoundtrackManifest.duration_sec"),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bpm": _finite_round(self.bpm, 2, "SoundtrackManifest.bpm"),
            "beats": [_finite_round(b, 3, "SoundtrackManifest.beat") for b in self.beats],
            "scene_cues": copy.deepcopy(self.scene_cues),
            "peak_dbfs": _finite_round(self.peak_dbfs, 2, "SoundtrackManifest.peak_dbfs"),
            "rms_dbfs": _finite_round(self.rms_dbfs, 2, "SoundtrackManifest.rms_dbfs"),
        }
