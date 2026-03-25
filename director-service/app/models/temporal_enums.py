"""Enumerations for temporal scene planning."""

from enum import Enum


class EventType(str, Enum):
    appear = "appear"
    disappear = "disappear"
    interaction = "interaction"
    direction_change = "direction_change"
    speed_change = "speed_change"
    occlusion_start = "occlusion_start"
    occlusion_end = "occlusion_end"


class TransitionType(str, Enum):
    cut = "cut"
    smooth = "smooth"
    match_cut = "match_cut"
    whip = "whip"


class PlanningPassType(str, Enum):
    style_intent = "style_intent"
    global_beat = "global_beat"
    shot_intent = "shot_intent"
    constraint_critique = "constraint_critique"
    deterministic_solve = "deterministic_solve"
    validation = "validation"
