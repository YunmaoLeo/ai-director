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


# --- Temporal geometry utilities ---


def interpolate_track_at_time(
    samples: list[dict],
    timestamp: float,
) -> Vec3:
    """Interpolate position from track samples at a given timestamp.

    Each sample dict must have 'timestamp' and 'position' keys.
    Returns linearly interpolated position.
    """
    if not samples:
        return (0.0, 0.0, 0.0)
    if len(samples) == 1:
        pos = samples[0]["position"]
        return (float(pos[0]), float(pos[1]), float(pos[2]))

    # Clamp to range
    if timestamp <= samples[0]["timestamp"]:
        pos = samples[0]["position"]
        return (float(pos[0]), float(pos[1]), float(pos[2]))
    if timestamp >= samples[-1]["timestamp"]:
        pos = samples[-1]["position"]
        return (float(pos[0]), float(pos[1]), float(pos[2]))

    # Find bracketing samples
    for i in range(len(samples) - 1):
        t0 = samples[i]["timestamp"]
        t1 = samples[i + 1]["timestamp"]
        if t0 <= timestamp <= t1:
            dt = t1 - t0
            if dt < 1e-9:
                pos = samples[i]["position"]
                return (float(pos[0]), float(pos[1]), float(pos[2]))
            t = (timestamp - t0) / dt
            p0 = samples[i]["position"]
            p1 = samples[i + 1]["position"]
            return vec3_lerp(
                (float(p0[0]), float(p0[1]), float(p0[2])),
                (float(p1[0]), float(p1[1]), float(p1[2])),
                t,
            )

    pos = samples[-1]["position"]
    return (float(pos[0]), float(pos[1]), float(pos[2]))


def compute_motion_descriptor(samples: list[dict]) -> dict:
    """Compute motion statistics from track samples.

    Returns a dict with keys: average_speed, max_speed, direction_trend,
    acceleration_bucket, total_displacement.
    """
    if len(samples) < 2:
        return {
            "average_speed": 0.0,
            "max_speed": 0.0,
            "direction_trend": (0.0, 0.0, 0.0),
            "acceleration_bucket": "constant",
            "total_displacement": 0.0,
        }

    speeds: list[float] = []
    total_distance = 0.0
    for i in range(1, len(samples)):
        p0 = samples[i - 1]["position"]
        p1 = samples[i]["position"]
        dt = samples[i]["timestamp"] - samples[i - 1]["timestamp"]
        d = vec3_distance(
            (float(p0[0]), float(p0[1]), float(p0[2])),
            (float(p1[0]), float(p1[1]), float(p1[2])),
        )
        total_distance += d
        speed = d / max(dt, 1e-9)
        speeds.append(speed)

    first_pos = samples[0]["position"]
    last_pos = samples[-1]["position"]
    displacement_vec = vec3_sub(
        (float(last_pos[0]), float(last_pos[1]), float(last_pos[2])),
        (float(first_pos[0]), float(first_pos[1]), float(first_pos[2])),
    )
    total_displacement = vec3_length(displacement_vec)
    direction_trend = vec3_normalize(displacement_vec) if total_displacement > 1e-6 else (0.0, 0.0, 0.0)

    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
    max_speed = max(speeds) if speeds else 0.0

    # Acceleration bucket: compare first-half vs second-half average speed
    half = len(speeds) // 2
    if half > 0:
        first_half_avg = sum(speeds[:half]) / half
        second_half_avg = sum(speeds[half:]) / max(len(speeds) - half, 1)
        ratio = second_half_avg / max(first_half_avg, 1e-9)
        if ratio > 1.3:
            accel_bucket = "accelerating"
        elif ratio < 0.7:
            accel_bucket = "decelerating"
        else:
            accel_bucket = "constant"
    else:
        accel_bucket = "constant"

    return {
        "average_speed": round(avg_speed, 4),
        "max_speed": round(max_speed, 4),
        "direction_trend": direction_trend,
        "acceleration_bucket": accel_bucket,
        "total_displacement": round(total_displacement, 4),
    }


def detect_keyframes(
    samples: list[dict],
    angle_threshold: float = 0.5,
    speed_threshold: float = 0.3,
) -> list[int]:
    """Detect keyframe indices where direction or speed changes significantly.

    Returns indices into the samples list.
    """
    if len(samples) < 3:
        return list(range(len(samples)))

    keyframes = [0]

    for i in range(1, len(samples) - 1):
        p_prev = samples[i - 1]["position"]
        p_curr = samples[i]["position"]
        p_next = samples[i + 1]["position"]

        d1 = vec3_sub(
            (float(p_curr[0]), float(p_curr[1]), float(p_curr[2])),
            (float(p_prev[0]), float(p_prev[1]), float(p_prev[2])),
        )
        d2 = vec3_sub(
            (float(p_next[0]), float(p_next[1]), float(p_next[2])),
            (float(p_curr[0]), float(p_curr[1]), float(p_curr[2])),
        )
        len1 = vec3_length(d1)
        len2 = vec3_length(d2)

        # Direction change check
        if len1 > 1e-6 and len2 > 1e-6:
            dot = vec3_dot(d1, d2) / (len1 * len2)
            dot = max(-1.0, min(1.0, dot))
            angle = math.acos(dot)
            if angle > angle_threshold:
                keyframes.append(i)
                continue

        # Speed change check
        dt1 = samples[i]["timestamp"] - samples[i - 1]["timestamp"]
        dt2 = samples[i + 1]["timestamp"] - samples[i]["timestamp"]
        speed1 = len1 / max(dt1, 1e-9)
        speed2 = len2 / max(dt2, 1e-9)
        avg_speed = (speed1 + speed2) / 2
        if avg_speed > 1e-6 and abs(speed2 - speed1) / avg_speed > speed_threshold:
            keyframes.append(i)

    keyframes.append(len(samples) - 1)
    return keyframes


def gaussian_smooth_points(points: list[Vec3], sigma: float = 1.0) -> list[Vec3]:
    """Apply Gaussian smoothing to a list of 3D points."""
    if len(points) < 3 or sigma <= 0:
        return list(points)

    # Build Gaussian kernel
    kernel_size = max(3, int(sigma * 4) | 1)  # Ensure odd
    if kernel_size % 2 == 0:
        kernel_size += 1
    half = kernel_size // 2

    kernel = []
    for k in range(-half, half + 1):
        kernel.append(math.exp(-0.5 * (k / sigma) ** 2))
    kernel_sum = sum(kernel)
    kernel = [k / kernel_sum for k in kernel]

    smoothed: list[Vec3] = []
    n = len(points)
    for i in range(n):
        sx, sy, sz = 0.0, 0.0, 0.0
        w_total = 0.0
        for j_offset, w in enumerate(kernel):
            idx = i + j_offset - half
            idx = max(0, min(n - 1, idx))
            sx += points[idx][0] * w
            sy += points[idx][1] * w
            sz += points[idx][2] * w
            w_total += w
        if w_total > 0:
            smoothed.append((sx / w_total, sy / w_total, sz / w_total))
        else:
            smoothed.append(points[i])

    # Preserve endpoints
    smoothed[0] = points[0]
    smoothed[-1] = points[-1]
    return smoothed
