"""Director policy profiles for scene-agnostic temporal planning."""

from typing import Tuple


_STYLE_PROFILES: dict[str, str] = {
    "balanced": (
        "Keep framing readable and context-aware with moderate movement intensity. "
        "Alternate orientation and emphasis shots, prefer match_cut/smooth for continuity, "
        "and reserve hard transitions for meaningful pivots."
    ),
    "dynamic_tracking": (
        "Prioritize lead-subject continuity under fast motion. Use anticipatory framing before direction/speed changes, "
        "mix dynamic tracking with brief stabilizing wides, and favor match_cut/whip/cut where momentum shifts."
    ),
    "narrative_reveal": (
        "Favor story progression and reveal timing. Build visual tension before key events, "
        "stage information with controlled pacing, and use reveal/detail framing as payoff."
    ),
    "subject_focus": (
        "Prioritize one primary subject with tighter composition and reduced context switching. "
        "Keep clear subject hierarchy and avoid unnecessary geography resets."
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
