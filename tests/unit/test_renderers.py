from __future__ import annotations

from pathlib import Path
import pytest
from PIL import ImageFont

from agy_codex_studio.hackathon_demos import (
    BENCHMIND_SCENES_SPEC,
    REDFLAG_SCENES_SPEC,
    BenchMindHackathonRenderer,
    RedFlagLoopHackathonRenderer,
    WidescreenHackathonRenderer,
    _load_font as load_wide_font,
    build_scene_caption_groups,
)
from agy_codex_studio.quad_showcase import (
    QUAD_SCENES_SPEC,
    QuadShowcaseRenderer,
    _load_font as load_quad_font,
    build_quad_caption_groups,
    get_quad_showcase_words,
)


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        (-5.0, 0.0),
        (0.0, 0.0),
        (0.5, 0.875),
        (1.0, 1.0),
        (9.0, 1.0),
    ],
)
def test_ease_out_cubic_clamping_and_curve(x: float, expected: float) -> None:
    assert QuadShowcaseRenderer._ease_out_cubic(x) == pytest.approx(expected)
    assert WidescreenHackathonRenderer._ease_out_cubic(x) == pytest.approx(expected)


def test_font_loaders_fallback_gracefully_when_fonts_missing(tmp_path: Path) -> None:
    f1 = load_quad_font(["nonexistent_font.ttf"], 24, fonts_dir=tmp_path)
    f2 = load_wide_font(["nonexistent_font.ttf"], 24, fonts_dir=tmp_path)
    assert f1 is not None
    assert f2 is not None

    # Corrupt font file triggers exception handler and falls back cleanly to default font
    bad_ttf = tmp_path / "corrupt.ttf"
    bad_ttf.write_bytes(b"not-a-valid-truetype-font")
    f3 = load_quad_font(["corrupt.ttf"], 20, fonts_dir=tmp_path)
    f4 = load_wide_font(["corrupt.ttf"], 20, fonts_dir=tmp_path)
    assert f3 is not None
    assert f4 is not None
    assert all(f.getbbox("Test")[2] > 0 for f in (f1, f2, f3, f4))


@pytest.mark.parametrize("neg_frame", [-1, -30, -900])
def test_renderers_reject_negative_frame_indices(neg_frame: int) -> None:
    quad = QuadShowcaseRenderer()
    bm = BenchMindHackathonRenderer()
    rf = RedFlagLoopHackathonRenderer()
    for r in (quad, bm, rf):
        with pytest.raises(ValueError, match="frame_idx"):
            r.render_frame(neg_frame)


@pytest.mark.parametrize("frame_idx", [0, 5, 45, 180, 185, 360, 540, 719, 800])
def test_all_renderers_produce_deterministic_rgb_frames_across_boundaries(frame_idx: int) -> None:
    default_loader = lambda _cands, _sz: ImageFont.load_default()
    quad = QuadShowcaseRenderer(font_loader=default_loader)
    bm = BenchMindHackathonRenderer(font_loader=default_loader)
    rf = RedFlagLoopHackathonRenderer(font_loader=default_loader)

    q_img = quad.render_frame(frame_idx)
    assert q_img.size == (1080, 1920)
    assert q_img.tobytes() == quad.render_frame(frame_idx).tobytes()

    bm_img = bm.render_frame(frame_idx)
    assert bm_img.size == (1920, 1080)

    rf_img = rf.render_frame(frame_idx)
    assert rf_img.size == (1920, 1080)


def test_caption_group_builders_monotonic_word_timings() -> None:
    for groups in (
        build_quad_caption_groups(),
        build_scene_caption_groups(BENCHMIND_SCENES_SPEC, "bm"),
        build_scene_caption_groups(REDFLAG_SCENES_SPEC, "rf"),
    ):
        assert len(groups) == 8
        for g in groups:
            assert g.start < g.end
            assert len(g.words) >= 2
            for i in range(len(g.words) - 1):
                assert g.words[i].start < g.words[i].end <= g.words[i + 1].start + 1e-6

    quad_words = get_quad_showcase_words()
    assert len(quad_words) > 30
