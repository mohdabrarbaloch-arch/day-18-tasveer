"""Tests for prompt analysis — the deterministic core of the engine."""

from app.engine.prompt import analyse, prompt_digest, tokenize


def test_tokenize_strips_stopwords_and_punctuation():
    tokens = tokenize("A photo of the lighthouse, at night!")
    assert "lighthouse" in tokens
    assert "night" in tokens
    # stopwords and the generic "photo" are removed
    assert "a" not in tokens
    assert "the" not in tokens
    assert "photo" not in tokens


def test_tokenize_keeps_hyphenated_words():
    assert "wide-angle" in tokenize("a wide-angle shot of a city")


def test_digest_is_stable_for_same_prompt():
    a = prompt_digest("a red fox in snow")
    b = prompt_digest("a red fox in snow")
    assert a == b


def test_digest_ignores_case_and_whitespace():
    assert prompt_digest("  A Red Fox  ") == prompt_digest("a red fox")


def test_digest_differs_for_different_prompts():
    assert prompt_digest("a red fox") != prompt_digest("a blue fox")


def test_digest_changes_with_negative_prompt():
    assert prompt_digest("a fox", "") != prompt_digest("a fox", "blurry")


def test_mood_words_shift_brightness():
    dark = analyse("a dark forest at night")
    bright = analyse("a bright sunny meadow")
    assert dark.brightness < bright.brightness


def test_warm_and_cold_push_hue_opposite_ways():
    warm = analyse("a warm golden sunset")
    cold = analyse("a cold icy winter")
    assert warm.hue_shift > cold.hue_shift


def test_composition_detects_portrait():
    plan = analyse("a portrait of a person")
    assert plan.composition == "centered"


def test_composition_detects_landscape():
    plan = analyse("a mountain landscape")
    assert plan.composition == "horizon"


def test_density_grows_with_prompt_length():
    short = analyse("a cat")
    long = analyse("a cat sitting on a windowsill watching rain fall over a quiet city street")
    assert long.density > short.density


def test_negative_prompt_simplifies_density():
    base = analyse("a busy market with many people and stalls")
    simple = analyse("a busy market with many people and stalls", "minimal clean")
    assert simple.density < base.density


def test_density_is_bounded():
    plan = analyse(" ".join(["word"] * 200))
    assert 0.15 <= plan.density <= 0.95


def test_subject_falls_back_when_prompt_is_all_stopwords():
    plan = analyse("a an the of")
    assert plan.subject == "untitled"
