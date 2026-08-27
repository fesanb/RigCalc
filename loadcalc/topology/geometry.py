import math


def distance_2d(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def parallel_angle_difference(a, b):
    difference = abs((a % 360.0) - (b % 360.0))
    difference = min(difference, 360.0 - difference)
    return abs(180.0 - difference) if difference > 90.0 else difference


def point_to_segment(point, start, end):
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
