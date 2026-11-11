"""Engine package: prompt analysis, style presets, and rendering."""

from app.engine.prompt import PromptPlan, analyse, prompt_digest, tokenize
from app.engine.renderer import (
    ASPECT_RATIOS,
    RenderResult,
    dimensions_for,
    render,
    render_grid,
)
from app.engine.styles import (
    DEFAULT_STYLE,
    STYLES,
    StylePreset,
    detect_style_from_prompt,
    get_style,
    list_styles,
)

__all__ = [
    "ASPECT_RATIOS",
    "DEFAULT_STYLE",
    "PromptPlan",
    "RenderResult",
    "STYLES",
    "StylePreset",
    "analyse",
    "detect_style_from_prompt",
    "dimensions_for",
    "get_style",
    "list_styles",
    "prompt_digest",
    "render",
    "render_grid",
    "tokenize",
]
