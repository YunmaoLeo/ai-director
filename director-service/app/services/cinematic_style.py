"""Director policy profiles for scene-agnostic temporal planning."""

from typing import Tuple


_STYLE_PROFILES: dict[str, str] = {
    "balanced": (
        "Keep framing readable and context-aware with moderate movement intensity and stable transitions."
    ),
    "dynamic_tracking": (
        "Prioritize subject continuity under fast motion. Use anticipatory framing and decisive but readable cuts."
    ),
    "narrative_reveal": (
        "Favor story progression and reveal moments. Build visual tension before key events."
    ),
    "subject_focus": (
        "Prioritize one primary subject with tighter composition and reduced context switching."
    ),
}


def normalize_style_profile(style_profile: str | None) -> str:
    if not style_profile:
        return "balanced"
    profile = style_profile.strip().lower()
    return profile if profile in _STYLE_PROFILES else "balanced"


def build_style_brief(style_profile: str | None, style_notes: str | None = None) -> Tuple[str, str]:
    profile = normalize_style_profile(style_profile)
    base = _STYLE_PROFILES[profile]
    notes = (style_notes or "").strip()
    if notes:
        return profile, f"{base}\nAdditional style notes: {notes}"
    return profile, base


def list_style_profiles() -> list[str]:
    return sorted(_STYLE_PROFILES.keys())
