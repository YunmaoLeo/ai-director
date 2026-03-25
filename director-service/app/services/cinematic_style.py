"""Cinematic style profiles for temporal planning prompts."""

from typing import Tuple


_STYLE_PROFILES: dict[str, str] = {
    "default": (
        "No special genre constraints. Keep motion readable, subject-focused, and spatially coherent."
    ),
    "motorsport_f1": (
        "Use F1 broadcast-inspired language and pacing. Prefer fast but legible tracking; "
        "prioritize lead subject continuity; use anticipatory framing before apex/turning moments; "
        "alternate between medium tracking, wide contextual shots, and selective reveal beats; "
        "avoid excessive whip transitions that break readability; preserve horizon stability when possible."
    ),
    "sports_broadcast": (
        "Use live sports broadcast style. Keep action center frame with clear context and timing continuity."
    ),
    "cinematic_drama": (
        "Use cinematic drama style: deliberate pacing, motivated reveals, and emotionally weighted framing."
    ),
}


def normalize_style_profile(style_profile: str | None) -> str:
    if not style_profile:
        return "default"
    profile = style_profile.strip().lower()
    return profile if profile in _STYLE_PROFILES else "default"


def build_style_brief(style_profile: str | None, style_notes: str | None = None) -> Tuple[str, str]:
    profile = normalize_style_profile(style_profile)
    base = _STYLE_PROFILES[profile]
    notes = (style_notes or "").strip()
    if notes:
        return profile, f"{base}\nAdditional style notes: {notes}"
    return profile, base


def list_style_profiles() -> list[str]:
    return sorted(_STYLE_PROFILES.keys())
