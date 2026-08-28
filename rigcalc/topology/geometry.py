import math


def distance_2d(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def distance_3d(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def parallel_angle_difference(a, b):
    difference = abs((a % 360.0) - (b % 360.0))
    difference = min(difference, 360.0 - difference)
    return abs(180.0 - difference) if difference > 90.0 else difference


def point_to_segment(point, start, end):
    dx = end.x - start.x
    dy = end.y - start.y
    dz = end.z - start.z
    length_sq = dx * dx + dy * dy + dz * dz
    if length_sq <= 1e-6:
        return distance_3d(point, start), 0.0, start.x, start.y, start.z
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy +
         (point.z - start.z) * dz) / length_sq
    t = max(0.0, min(1.0, t))
    qx, qy, qz = start.x + t * dx, start.y + t * dy, start.z + t * dz
    projected = type(point)(qx, qy, qz)
    return distance_3d(point, projected), t, qx, qy, qz


def point_to_segment_2d(point, start, end):
    """Plan projection for PIOs whose insertion Z is not a hanging point."""
    dx = end.x - start.x
    dy = end.y - start.y
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-6:
        return distance_2d(point, start), 0.0, start.x, start.y
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    qx, qy = start.x + t * dx, start.y + t * dy
    return math.hypot(point.x - qx, point.y - qy), t, qx, qy


def bbox_distance(point, bbox):
    x1, x2 = sorted((bbox.first.x, bbox.second.x))
    y1, y2 = sorted((bbox.first.y, bbox.second.y))
    dx = max(x1 - point.x, 0.0, point.x - x2)
    dy = max(y1 - point.y, 0.0, point.y - y2)
    return math.hypot(dx, dy)
