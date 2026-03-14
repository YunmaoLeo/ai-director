"""Geometry utilities for 2.5D camera planning.

Coordinate system: Unity left-handed (X=right, Y=up, Z=forward).
Most operations work on the XZ plane with Y as height.
"""

import math
from typing import Sequence

import numpy as np

Vec3 = tuple[float, float, float]


def vec3_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec3_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec3_scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def vec3_length(v: Vec3) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def vec3_normalize(v: Vec3) -> Vec3:
    length = vec3_length(v)
    if length < 1e-9:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def vec3_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vec3_distance(a: Vec3, b: Vec3) -> float:
    return vec3_length(vec3_sub(a, b))


def vec3_lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def xz_distance(a: Vec3, b: Vec3) -> float:
    dx = a[0] - b[0]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dz * dz)


def aabb_contains_xz(
    point: Vec3, obj_pos: Vec3, obj_size: Vec3, margin: float = 0.0
) -> bool:
    """Check if a point (XZ) is inside an object's AABB plus margin."""
    half_w = obj_size[0] / 2 + margin
    half_d = obj_size[2] / 2 + margin
    return (
        abs(point[0] - obj_pos[0]) <= half_w
        and abs(point[2] - obj_pos[2]) <= half_d
    )


def aabb_pushback_xz(
    point: Vec3, obj_pos: Vec3, obj_size: Vec3, margin: float = 0.3
) -> Vec3:
    """Push a point outside an object's AABB on the XZ plane."""
    half_w = obj_size[0] / 2 + margin
    half_d = obj_size[2] / 2 + margin

    dx = point[0] - obj_pos[0]
    dz = point[2] - obj_pos[2]

    # Find which face is closest to push out to
    overlap_x = half_w - abs(dx)
    overlap_z = half_d - abs(dz)

    if overlap_x <= 0 or overlap_z <= 0:
        return point  # Not inside

    if overlap_x < overlap_z:
        new_x = obj_pos[0] + (half_w if dx >= 0 else -half_w)
        return (new_x, point[1], point[2])
    else:
        new_z = obj_pos[2] + (half_d if dz >= 0 else -half_d)
        return (point[0], point[1], new_z)


def clamp_to_bounds(point: Vec3, width: float, length: float, margin: float = 0.3) -> Vec3:
    """Clamp point to scene bounds on XZ plane. Bounds: [0, width] x [0, length]."""
    return (
        max(margin, min(width - margin, point[0])),
        point[1],
        max(margin, min(length - margin, point[2])),
    )


def arc_points(
    center: Vec3,
    radius: float,
    start_angle: float,
    end_angle: float,
    num_points: int,
    height: float | None = None,
) -> list[Vec3]:
    """Generate points along a circular arc on the XZ plane around center."""
    points = []
    y = height if height is not None else center[1]
    for i in range(num_points):
        t = i / max(1, num_points - 1)
        angle = start_angle + (end_angle - start_angle) * t
        x = center[0] + radius * math.cos(angle)
        z = center[2] + radius * math.sin(angle)
        points.append((x, y, z))
    return points


def bezier_quadratic(p0: Vec3, p1: Vec3, p2: Vec3, num_points: int) -> list[Vec3]:
    """Generate points along a quadratic Bezier curve."""
    points = []
    for i in range(num_points):
        t = i / max(1, num_points - 1)
        inv = 1.0 - t
        x = inv * inv * p0[0] + 2 * inv * t * p1[0] + t * t * p2[0]
        y = inv * inv * p0[1] + 2 * inv * t * p1[1] + t * t * p2[1]
        z = inv * inv * p0[2] + 2 * inv * t * p1[2] + t * t * p2[2]
        points.append((x, y, z))
    return points


def linear_points(start: Vec3, end: Vec3, num_points: int) -> list[Vec3]:
    """Generate evenly spaced points along a line."""
    return [vec3_lerp(start, end, i / max(1, num_points - 1)) for i in range(num_points)]


def compute_look_direction(camera_pos: Vec3, target_pos: Vec3) -> Vec3:
    """Compute normalized direction from camera to target."""
    return vec3_normalize(vec3_sub(target_pos, camera_pos))


def centroid(positions: Sequence[Vec3]) -> Vec3:
    """Compute the centroid of a set of 3D positions."""
    if not positions:
        return (0.0, 0.0, 0.0)
    n = len(positions)
    sx = sum(p[0] for p in positions)
    sy = sum(p[1] for p in positions)
    sz = sum(p[2] for p in positions)
    return (sx / n, sy / n, sz / n)
