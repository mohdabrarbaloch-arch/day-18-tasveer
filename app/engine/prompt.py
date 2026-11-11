"""Prompt analysis.

Turns a free-text prompt into a small structured plan the renderer can act on:
a palette shift, a composition bias, and a density value. This is deliberately
deterministic — the same prompt always yields the same plan, which is what makes
seeds reproducible.
"""

import hashlib
import re
from dataclasses import dataclass

# Words that push the palette in a direction. Value is (hue_shift, saturation,
# brightness) in a -1..1 range.
MOOD_WORDS: dict[str, tuple[float, float, float]] = {
    "warm": (0.15, 0.15, 0.05),
    "sunset": (0.2, 0.2, 0.0),
    "golden": (0.18, 0.1, 0.1),
    "fire": (0.25, 0.3, 0.0),
    "cold": (-0.2, -0.05, 0.0),
    "ice": (-0.25, -0.1, 0.1),
    "winter": (-0.22, -0.15, 0.05),
    "night": (-0.1, 0.05, -0.25),
    "dark": (0.0, 0.0, -0.3),
    "bright": (0.0, 0.1, 0.25),
    "pastel": (0.05, -0.3, 0.2),
    "vivid": (0.0, 0.35, 0.05),
    "muted": (0.0, -0.35, -0.05),
    "calm": (-0.05, -0.2, 0.05),
    "storm": (-0.15, 0.1, -0.2),
    "forest": (-0.3, 0.05, -0.05),
    "ocean": (-0.35, 0.1, 0.0),
    "desert": (0.22, 0.05, 0.1),
    "neon": (0.1, 0.45, 0.1),
}

# Words that bias composition.
COMPOSITION_WORDS: dict[str, str] = {
    "portrait": "centered",
    "face": "centered",
    "person": "centered",
    "character": "centered",
    "landscape": "horizon",
    "mountain": "horizon",
    "sea": "horizon",
    "city": "horizon",
    "skyline": "horizon",
    "abstract": "scatter",
    "pattern": "scatter",
    "texture": "scatter",
    "product": "centered",
    "object": "centered",
}

STOPWORDS = {
    "a",
    "an",
    "the",
    "of",
    "in",
    "on",
    "at",
    "with",
    "and",
    "or",
    "for",
    "to",
    "by",
    "from",
    "is",
    "are",
    "very",
    "highly",
    "detailed",
    "style",
    "photo",
    "image",
    "picture",
    "render",
    "shot",
    "view",
}


@dataclass(frozen=True)
class PromptPlan:
    """What the renderer needs to know about a prompt."""

    tokens: tuple[str, ...]
    hue_shift: float
    saturation: float
    brightness: float
    composition: str
    density: float
    digest: int

    @property
    def subject(self) -> str:
        """The most meaningful word in the prompt, for labelling."""
        return self.tokens[0] if self.tokens else "untitled"


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def tokenize(prompt: str) -> list[str]:
    """Lowercase word tokens, stopwords and punctuation removed."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", prompt.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def prompt_digest(prompt: str, negative: str = "") -> int:
    """Stable 32-bit integer derived from the prompt text."""
    payload = f"{prompt.strip().lower()}|{negative.strip().lower()}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def analyse(prompt: str, negative: str = "") -> PromptPlan:
    """Build a PromptPlan from a prompt and its negative prompt."""
    tokens = tokenize(prompt)
    lowered = prompt.lower()

    hue = sat = bright = 0.0
    for word, (h, s, b) in MOOD_WORDS.items():
        if word in lowered:
            hue += h
            sat += s
            bright += b

    composition = "scatter"
    for word, comp in COMPOSITION_WORDS.items():
        if word in lowered:
            composition = comp
            break

    # Longer, more specific prompts get denser compositions — up to a point.
    density = _clamp(0.35 + len(tokens) * 0.045, 0.2, 0.95)

    # A negative prompt asking for "simple" or "minimal" thins things out.
    if any(w in negative.lower() for w in ("simple", "minimal", "clean", "empty")):
        density = _clamp(density - 0.25, 0.15, 0.95)

    return PromptPlan(
        tokens=tuple(tokens),
        hue_shift=_clamp(hue),
        saturation=_clamp(sat),
        brightness=_clamp(bright),
        composition=composition,
        density=density,
        digest=prompt_digest(prompt, negative),
    )
