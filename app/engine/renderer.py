"""The renderer.

This is a deterministic procedural image engine, not a diffusion model. It
builds a real image from the prompt's plan and the style preset: fractal noise
(fBm) warped by domain distortion, mapped through the style's palette, then
finished with light accumulation, vignette and grain.

Why procedural rather than a neural net? Because it runs in well under a second
on a plain CPU, needs no GPU and no API key, and — most importantly — it is
honest. Every pixel is a pure function of the prompt and the seed, so the same
inputs always produce byte-identical output. When you want diffusion-quality
output, set IMAGE_PROVIDER to "openai" or "replicate" and the same API will
delegate to a hosted model.

The result reads as abstract editorial art: the kind of thing you'd put behind
a headline. That is the right bar for a style-preview surface.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from app.engine.prompt import PromptPlan
from app.engine.styles import StylePreset

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "3:2": (1216, 812),
    "2:3": (812, 1216),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "4:5": (900, 1125),
}

DEFAULT_ASPECT = "1:1"


@dataclass(frozen=True)
class RenderResult:
    path: Path
    width: int
    height: int
    seed: int


# --------------------------------------------------------------------------
# Noise
# --------------------------------------------------------------------------


def _value_noise(width: int, height: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth value noise: a tiny random grid, bicubic-upscaled."""
    cells = max(2, cells)
    grid = rng.random((cells, cells)).astype(np.float32)
    img = Image.fromarray((grid * 255).astype(np.uint8), mode="L")
    img = img.resize((width, height), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _fbm(
    width: int,
    height: int,
    rng: np.random.Generator,
    octaves: int = 5,
    base_cells: int = 3,
    persistence: float = 0.5,
) -> np.ndarray:
    """Fractal Brownian motion — layered noise at doubling frequencies."""
    total = np.zeros((height, width), dtype=np.float32)
    amplitude = 1.0
    norm = 0.0
    cells = base_cells
    for _ in range(octaves):
        total += _value_noise(width, height, cells, rng) * amplitude
        norm += amplitude
        amplitude *= persistence
        cells *= 2
    return total / max(norm, 1e-6)


def _ridge(noise: np.ndarray, sharpness: float = 1.6) -> np.ndarray:
    """Turn smooth noise into ridged, creased forms."""
    return 1.0 - np.abs(noise * 2.0 - 1.0) ** sharpness


def _normalise(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-6:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


# --------------------------------------------------------------------------
# Colour
# --------------------------------------------------------------------------


def _hex_to_unit(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return np.array([int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)


def _rgb_to_hsl(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.max(rgb, axis=-1)
    mn = np.min(rgb, axis=-1)
    lightness = (mx + mn) / 2.0
    delta = mx - mn
    saturation = np.where(
        delta < 1e-6, 0.0, delta / np.where(lightness < 0.5, mx + mn, 2.0 - mx - mn)
    )
    hue = np.zeros_like(mx)
    mask = delta > 1e-6
    idx = mask & (mx == r)
    hue[idx] = ((g[idx] - b[idx]) / delta[idx]) % 6.0
    idx = mask & (mx == g)
    hue[idx] = ((b[idx] - r[idx]) / delta[idx]) + 2.0
    idx = mask & (mx == b)
    hue[idx] = ((r[idx] - g[idx]) / delta[idx]) + 4.0
    return np.stack([hue / 6.0, saturation, lightness], axis=-1)


def _hsl_to_rgb(hsl: np.ndarray) -> np.ndarray:
    """Vectorised HSL -> RGB. Standard channel formula, no branches."""
    h, s, lightness = hsl[..., 0], hsl[..., 1], hsl[..., 2]
    a = s * np.minimum(lightness, 1.0 - lightness)
    out = np.zeros_like(hsl)
    for i, n in enumerate([0.0, 8.0, 4.0]):
        k = (n + h * 12.0) % 12.0
        out[..., i] = lightness - a * np.maximum(
            -1.0, np.minimum(np.minimum(k - 3.0, 9.0 - k), 1.0)
        )
    return np.clip(out, 0.0, 1.0)


def _apply_mood(palette: np.ndarray, plan: PromptPlan) -> np.ndarray:
    """Shift the whole palette's hue/saturation/brightness by the prompt's mood."""
    hsl = _rgb_to_hsl(palette)
    hsl[..., 0] = (hsl[..., 0] + plan.hue_shift * 0.35) % 1.0
    hsl[..., 1] = np.clip(hsl[..., 1] * (1.0 + plan.saturation * 0.7), 0.0, 1.0)
    hsl[..., 2] = np.clip(hsl[..., 2] * (1.0 + plan.brightness * 0.55), 0.0, 1.0)
    return _hsl_to_rgb(hsl)


def _map_palette(t: np.ndarray, stops: np.ndarray) -> np.ndarray:
    """Map a 0-1 field onto a multi-stop gradient. Returns (H, W, 3)."""
    n = len(stops)
    scaled = np.clip(t, 0.0, 0.999999) * (n - 1)
    idx = np.floor(scaled).astype(np.int32)
    frac = (scaled - idx)[..., None]
    lo = stops[idx]
    hi = stops[np.minimum(idx + 1, n - 1)]
    return lo + (hi - lo) * frac


# --------------------------------------------------------------------------
# Layers
# --------------------------------------------------------------------------


def _background(width: int, height: int, stops: np.ndarray, mode: str) -> np.ndarray:
    """A smooth base field before any texture is added."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    if mode == "radial":
        cx, cy = width / 2.0, height / 2.0
        d = np.sqrt(((xx - cx) / width) ** 2 + ((yy - cy) / height) ** 2)
        t = _normalise(d)
    elif mode == "linear":
        t = yy / max(1.0, height - 1.0)
    else:  # diagonal
        t = _normalise(xx / max(1.0, width - 1.0) + yy / max(1.0, height - 1.0))
    return _map_palette(t.astype(np.float32), stops)


def _texture(
    width: int,
    height: int,
    plan: PromptPlan,
    preset: StylePreset,
    rng: np.random.Generator,
) -> np.ndarray:
    """The warped fBm field that gives the image its form."""
    octaves = 6 if preset.softness > 1.3 else 5
    base_cells = int(3 + plan.density * 5)

    # Domain warping: displace the sampling of a second noise field by the
    # first. This is what makes the forms look organic instead of cloudy.
    warp = _fbm(width, height, rng, octaves=3, base_cells=max(2, base_cells // 2))
    warp2 = _fbm(width, height, rng, octaves=3, base_cells=max(2, base_cells // 2))

    strength = 0.35 + plan.density * 0.55
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    xs = np.clip(xx + (warp - 0.5) * width * 0.22 * strength, 0, width - 1).astype(np.int32)
    ys = np.clip(yy + (warp2 - 0.5) * height * 0.22 * strength, 0, height - 1).astype(np.int32)

    field = _fbm(width, height, rng, octaves=octaves, base_cells=base_cells)
    warped = field[ys, xs]

    # Blend in ridge detail — this is the "brush stroke" quality.
    detail = _ridge(_fbm(width, height, rng, octaves=4, base_cells=base_cells * 2))
    warped = warped * 0.72 + detail * 0.28

    return _normalise(warped.astype(np.float32))


def _light_direction(width: int, height: int, rng: np.random.Generator) -> np.ndarray:
    """A soft directional light gradient, as if a key light sits off-frame."""
    angle = rng.uniform(0, math.tau)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xx / max(1.0, width - 1.0)) - 0.5
    ny = (yy / max(1.0, height - 1.0)) - 0.5
    d = nx * math.cos(angle) + ny * math.sin(angle)
    return _normalise(d)


def _vignette_mask(width: int, height: int, strength: float) -> np.ndarray:
    """0 at the corners, 1 in the centre, smooth in between."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xx - width / 2.0) / (width / 2.0)
    ny = (yy - height / 2.0) / (height / 2.0)
    r = np.sqrt(nx * nx + ny * ny) / math.sqrt(2.0)
    mask = np.clip(1.0 - (r**2) * strength * 1.6, 0.0, 1.0)
    return mask[..., None]


def _grain(width: int, height: int, amount: float, rng: np.random.Generator) -> np.ndarray:
    """Fine film grain — per-pixel, slightly smoothed."""
    noise = rng.normal(0.0, 1.0, (height, width)).astype(np.float32)
    noise = noise * 0.5 + 0.5
    img = Image.fromarray((np.clip(noise, 0, 1) * 255).astype(np.uint8), "L")
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    return (np.asarray(img, dtype=np.float32) / 255.0 - 0.5)[..., None] * amount


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------


def dimensions_for(aspect: str, max_pixels: int) -> tuple[int, int]:
    """Resolve an aspect ratio to pixel dimensions, capped by a pixel budget."""
    width, height = ASPECT_RATIOS.get(aspect, ASPECT_RATIOS[DEFAULT_ASPECT])
    if width * height > max_pixels:
        scale = math.sqrt(max_pixels / (width * height))
        width = max(64, int(width * scale) // 2 * 2)
        height = max(64, int(height * scale) // 2 * 2)
    return width, height


def render(
    prompt: str,
    plan: PromptPlan,
    preset: StylePreset,
    seed: int,
    aspect: str,
    out_path: Path,
    max_pixels: int = 4_000_000,
) -> RenderResult:
    """Render one image and write it to `out_path` as a PNG."""
    width, height = dimensions_for(aspect, max_pixels)
    rng = np.random.default_rng(seed % (2**32))

    stops = np.stack([_hex_to_unit(c) for c in preset.palette])
    stops = _apply_mood(stops, plan)

    # 1. Base gradient.
    canvas = _background(width, height, stops, preset.gradient)

    # 2. Warped fractal field mapped through the palette.
    field = _texture(width, height, plan, preset, rng)
    textured = _map_palette(field, stops)

    # 3. Accumulate: the texture carries most of the image, the gradient
    #    underneath keeps it from going flat.
    canvas = canvas * 0.42 + textured * 0.58

    # 4. Directional key light.
    light = _light_direction(width, height, rng)[..., None]
    canvas = canvas * (0.82 + light * 0.34)

    # 5. A soft bloom over the brightest region — this is what stops it looking
    #    like a texture swatch and starts it looking like a photograph.
    lum = canvas.mean(axis=-1, keepdims=True)
    bloom = np.clip((lum - 0.55) * 2.2, 0.0, 1.0) ** 1.5
    bloom_img = Image.fromarray((np.clip(bloom[..., 0], 0, 1) * 255).astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(max(2, width // 70))
    )
    bloom_soft = np.asarray(bloom_img, dtype=np.float32)[..., None] / 255.0
    canvas = canvas + bloom_soft * 0.22

    # 6. Vignette and grain.
    canvas = canvas * _vignette_mask(width, height, preset.vignette)
    canvas = canvas + _grain(width, height, preset.grain, rng)

    # 7. A gentle S-curve for contrast. Formula from the classic "smoothstep"
    #    contrast adjustment — keeps highlights from clipping to white.
    canvas = np.clip(canvas, 0.0, 1.0)
    canvas = canvas * canvas * (3.0 - 2.0 * canvas) * 0.55 + canvas * 0.45
    canvas = np.clip(canvas, 0.0, 1.0)

    image = Image.fromarray((canvas * 255.0).astype(np.uint8), mode="RGB")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG", optimize=True)

    return RenderResult(path=out_path, width=width, height=height, seed=seed)


def render_grid(
    prompt: str,
    plan: PromptPlan,
    preset: StylePreset,
    base_seed: int,
    aspect: str,
    out_dir: Path,
    count: int = 4,
    max_pixels: int = 4_000_000,
) -> list[RenderResult]:
    """Render `count` variations, each with a derived seed."""
    results = []
    for i in range(count):
        # Derive a distinct but reproducible seed per tile.
        seed = (base_seed + i * 7919) % (2**31 - 1)
        path = out_dir / f"img_{i}.png"
        results.append(render(prompt, plan, preset, seed, aspect, path, max_pixels))
    return results
