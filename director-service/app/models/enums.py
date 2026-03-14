from enum import Enum


class ShotType(str, Enum):
    establishing = "establishing"
    wide = "wide"
    medium = "medium"
    close_up = "close_up"
    detail = "detail"
    reveal = "reveal"


class Movement(str, Enum):
    static = "static"
    slow_forward = "slow_forward"
    slow_backward = "slow_backward"
    lateral_slide = "lateral_slide"
    arc = "arc"
    pan = "pan"
    orbit = "orbit"


class Pacing(str, Enum):
    calm = "calm"
    steady = "steady"
    dramatic = "dramatic"
    deliberate = "deliberate"


class PathType(str, Enum):
    linear = "linear"
    bezier = "bezier"
    arc = "arc"
