"""Tests for style presets and the renderer."""

from pathlib import Path

import pytest
from PIL import Image

from app.engine.prompt import analyse
from app.engine.renderer import dimensions_for, render, render_grid
from app.engine.styles import (
    DEFAULT_STYLE,
    STYLES,
    detect_style_from_prompt,
    get_style,
    list_styles,
)


def test_every_style_has_a_full_palette():
    for style in STYLES.values():
        assert len(style.palette) >= 4
        for colour in style.palette:
            assert colour.startswith("#")
            assert len(colour) == 7


def test_get_style_falls_back_to_default():
    assert get_style("does-not-exist").key == DEFAULT_STYLE
    assert get_style(None).key == DEFAULT_STYLE


def test_get_style_is_case_insensitive():
    assert get_style("CYBERPUNK").key == "cyberpunk"


def test_list_styles_returns_all():
    assert len(list_styles()) == len(STYLES)


def test_detect_style_from_prompt_matches_keyword():
    assert detect_style_from_prompt("a neon cyberpunk street") == "cyberpunk"
    assert detect_style_from_prompt("a soft watercolor wash") == "watercolor"


def test_detect_style_defaults_when_no_keyword():
    assert detect_style_from_prompt("a plain object") == DEFAULT_STYLE


@pytest.mark.parametrize(
    "aspect,expected",
    [("1:1", (1024, 1024)), ("16:9", (1280, 720)), ("9:16", (720, 1280))],
)
def test_dimensions_for_known_ratios(aspect, expected):
    assert dimensions_for(aspect, 4_000_000) == expected


def test_dimensions_for_unknown_ratio_uses_default():
    assert dimensions_for("7:3", 4_000_000) == dimensions_for("1:1", 4_000_000)


def test_dimensions_respect_pixel_budget():
    width, height = dimensions_for("16:9", 100_000)
    assert width * height <= 100_000


def test_render_writes_a_real_png(tmp_path: Path):
    plan = analyse("a lighthouse at night")
    preset = get_style("cinematic")
    out = tmp_path / "one.png"

    result = render("a lighthouse at night", plan, preset, 42, "1:1", out)

    assert out.exists()
    assert out.stat().st_size > 5_000  # a real image, not an empty file
    assert result.width == 1024 and result.height == 1024

    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.size == (1024, 1024)
        assert img.mode == "RGB"


def test_render_is_deterministic(tmp_path: Path):
    """Same prompt + same seed must produce byte-identical output."""
    plan = analyse("a red fox in snow")
    preset = get_style("minimal")

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    render("a red fox in snow", plan, preset, 777, "1:1", a)
    render("a red fox in snow", plan, preset, 777, "1:1", b)

    assert a.read_bytes() == b.read_bytes()


def test_different_seeds_produce_different_images(tmp_path: Path):
    plan = analyse("a red fox in snow")
    preset = get_style("minimal")

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    render("a red fox in snow", plan, preset, 1, "1:1", a)
    render("a red fox in snow", plan, preset, 2, "1:1", b)

    assert a.read_bytes() != b.read_bytes()


def test_render_grid_produces_distinct_tiles(tmp_path: Path):
    plan = analyse("a quiet harbour at dawn")
    preset = get_style("watercolor")

    results = render_grid("a quiet harbour at dawn", plan, preset, 100, "1:1", tmp_path, count=4)

    assert len(results) == 4
    seeds = {r.seed for r in results}
    assert len(seeds) == 4, "each tile must get its own seed"

    payloads = {r.path.read_bytes() for r in results}
    assert len(payloads) == 4, "each tile must be visually distinct"


def test_render_output_is_not_a_flat_colour(tmp_path: Path):
    """Guard against a renderer that silently produces a blank canvas."""
    plan = analyse("a stormy sea")
    preset = get_style("cinematic")
    out = tmp_path / "flat.png"
    render("a stormy sea", plan, preset, 5, "1:1", out)

    with Image.open(out) as img:
        colours = img.convert("RGB").getcolors(maxcolors=1_000_000)
    assert colours is not None
    assert len(colours) > 500, "image should have real tonal variation"
