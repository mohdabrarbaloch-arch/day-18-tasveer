"""Style presets.

Each preset is a complete visual recipe: a palette, a composition bias, and
render parameters. The renderer reads these and nothing else, so adding a new
style is a data change, not a code change.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StylePreset:
    key: str
    label: str
    # Ordered colour stops, hex. First is the dominant background.
    palette: tuple[str, ...]
    # How many soft light blobs to layer.
    blobs: int = 5
    # Blob radius as a fraction of the short edge.
    blob_radius: tuple[float, float] = (0.25, 0.65)
    # Strength of the geometric accent layer, 0 disables it.
    accent: float = 0.5
    # Grain amount, 0-1.
    grain: float = 0.06
    # Vignette strength, 0-1.
    vignette: float = 0.35
    # Background gradient mode: "linear" | "radial" | "diagonal".
    gradient: str = "diagonal"
    # Extra blur applied to the blob layer, in pixels at 1024px.
    softness: float = 1.0
    keywords: tuple[str, ...] = field(default_factory=tuple)


STYLES: dict[str, StylePreset] = {
    "cinematic": StylePreset(
        key="cinematic",
        label="Cinematic",
        palette=("#0b1020", "#1b2a4a", "#c9762f", "#f2c14e", "#e8e3d9"),
        blobs=6,
        blob_radius=(0.3, 0.7),
        accent=0.55,
        grain=0.07,
        vignette=0.45,
        gradient="diagonal",
        softness=1.2,
        keywords=("cinematic", "film", "dramatic", "moody"),
    ),
    "anime": StylePreset(
        key="anime",
        label="Anime",
        palette=("#fdf6f0", "#ffd6e0", "#8ecae6", "#219ebc", "#023047"),
        blobs=5,
        blob_radius=(0.2, 0.5),
        accent=0.7,
        grain=0.03,
        vignette=0.2,
        gradient="radial",
        softness=0.8,
        keywords=("anime", "manga", "cel", "illustration"),
    ),
    "oil": StylePreset(
        key="oil",
        label="Oil Painting",
        palette=("#2b1d14", "#6b4423", "#a8763e", "#d9b382", "#f0e2c8"),
        blobs=7,
        blob_radius=(0.25, 0.6),
        accent=0.35,
        grain=0.12,
        vignette=0.4,
        gradient="linear",
        softness=1.6,
        keywords=("oil", "painting", "brush", "canvas", "classical"),
    ),
    "cyberpunk": StylePreset(
        key="cyberpunk",
        label="Cyberpunk",
        palette=("#05010d", "#1a0b2e", "#ff2a6d", "#05d9e8", "#d1f7ff"),
        blobs=6,
        blob_radius=(0.2, 0.55),
        accent=0.85,
        grain=0.08,
        vignette=0.5,
        gradient="diagonal",
        softness=0.9,
        keywords=("cyberpunk", "neon", "futuristic", "tech", "synth"),
    ),
    "minimal": StylePreset(
        key="minimal",
        label="Minimal",
        palette=("#fafafa", "#e8e8e8", "#c9c9c9", "#2b2b2b", "#111111"),
        blobs=3,
        blob_radius=(0.3, 0.6),
        accent=0.25,
        grain=0.02,
        vignette=0.12,
        gradient="linear",
        softness=1.4,
        keywords=("minimal", "clean", "simple", "white", "scandinavian"),
    ),
    "watercolor": StylePreset(
        key="watercolor",
        label="Watercolour",
        palette=("#fbf8f3", "#cfe3e8", "#a8c8b8", "#e8b4a0", "#6b7f8c"),
        blobs=8,
        blob_radius=(0.2, 0.55),
        accent=0.2,
        grain=0.05,
        vignette=0.18,
        gradient="radial",
        softness=2.0,
        keywords=("watercolor", "watercolour", "soft", "wash", "pastel"),
    ),
    "render3d": StylePreset(
        key="render3d",
        label="3D Render",
        palette=("#0e1116", "#232a36", "#4a5568", "#8fa3bf", "#e6edf7"),
        blobs=5,
        blob_radius=(0.25, 0.6),
        accent=0.6,
        grain=0.04,
        vignette=0.3,
        gradient="radial",
        softness=1.0,
        keywords=("3d", "render", "octane", "blender", "product"),
    ),
    "noir": StylePreset(
        key="noir",
        label="Noir",
        palette=("#08080a", "#1c1c20", "#3a3a42", "#8a8a94", "#e4e4e8"),
        blobs=4,
        blob_radius=(0.3, 0.7),
        accent=0.4,
        grain=0.14,
        vignette=0.6,
        gradient="diagonal",
        softness=1.3,
        keywords=("noir", "black and white", "monochrome", "shadow"),
    ),
}

DEFAULT_STYLE = "cinematic"


def get_style(key: str | None) -> StylePreset:
    """Resolve a style key, falling back to the default rather than raising."""
    if not key:
        return STYLES[DEFAULT_STYLE]
    return STYLES.get(key.strip().lower(), STYLES[DEFAULT_STYLE])


def list_styles() -> list[dict]:
    return [{"key": s.key, "label": s.label, "palette": list(s.palette)} for s in STYLES.values()]


def detect_style_from_prompt(prompt: str) -> str:
    """Pick the style whose keywords appear in the prompt, if any."""
    lowered = prompt.lower()
    best_key, best_hits = DEFAULT_STYLE, 0
    for style in STYLES.values():
        hits = sum(1 for kw in style.keywords if kw in lowered)
        if hits > best_hits:
            best_key, best_hits = style.key, hits
    return best_key
