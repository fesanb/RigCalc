from rigcalc import config
from rigcalc.model.construction import Connection

from .geometry import bbox_distance, distance_3d, parallel_angle_difference, point_to_segment


def _endpoint_pairs(a, b):
    return (
        ("start", a.start, "start", b.start),
        ("start", a.start, "end", b.end),
        ("end", a.end, "start", b.start),
        ("end", a.end, "end", b.end),
    )


def find_line_line_connection(a, b):
    candidates = sorted(
        (distance_3d(ap, bp), aport, bport)
        for aport, ap, bport, bp in _endpoint_pairs(a, b)
    )
    distance, aport, bport = candidates[0]
    if distance <= config.ENDPOINT_TOLERANCE_MM:
        return Connection(a.id, b.id, aport, bport, "endpoint", distance, "EXACT")

    if parallel_angle_difference(a.z_rotation_deg, b.z_rotation_deg) > config.COLLINEAR_ANGLE_TOLERANCE_DEG:
        return None

    relaxed = []
    for aport, point, other in (("start", a.start, b), ("end", a.end, b)):
        lateral, _, _, _, _ = point_to_segment(point, other.start, other.end)
        distances = ((distance_3d(point, other.start), "start"),
                     (distance_3d(point, other.end), "end"))
        longitudinal, bport = min(distances)
        if lateral <= config.COLLINEAR_LATERAL_TOLERANCE_MM and longitudinal <= config.COLLINEAR_LONGITUDINAL_TOLERANCE_MM:
            relaxed.append((longitudinal, aport, bport))
    for bport, point, other in (("start", b.start, a), ("end", b.end, a)):
        lateral, _, _, _, _ = point_to_segment(point, other.start, other.end)
        distances = ((distance_3d(point, other.start), "start"),
                     (distance_3d(point, other.end), "end"))
        longitudinal, aport = min(distances)
        if lateral <= config.COLLINEAR_LATERAL_TOLERANCE_MM and longitudinal <= config.COLLINEAR_LONGITUDINAL_TOLERANCE_MM:
            relaxed.append((longitudinal, aport, bport))
    if not relaxed:
        return None
    distance, aport, bport = sorted(relaxed)[0]
    return Connection(a.id, b.id, aport, bport, "inferred_collinear", distance, "INFERRED", distance)


def _corner_reach_mm(line):
    size = max(line.width_mm, line.height_mm, 0.0)
    return max(config.CORNER_TOLERANCE_MM,
               config.CORNER_ENDPOINT_REACH_FACTOR*size)


def find_corner_connections(axis_items, corners):
    """Join each axis end to its nearest corner block in 3D.

    Corner items carry no chord, and their 2D bounding box is view-dependent
    and ignores elevation, so it must not decide structural connectivity.
    """
    connections = []
    for line in axis_items:
        for port, point in (("start", line.start), ("end", line.end)):
            candidates = sorted(
                (distance_3d(point, corner.position), corner.id, corner)
                for corner in corners)
            if not candidates:
                continue
            distance, _, corner = candidates[0]
            if distance > _corner_reach_mm(line):
                continue
            connections.append(Connection(
                line.id, corner.id, port, "corner", "line_to_corner",
                distance, "EXACT"))
    return connections


def find_arc_connection(a, b):
    """Endpoint connection for members of which at least one is curved."""
    candidates = sorted(
        (distance_3d(ap, bp), aport, bport)
        for aport, ap, bport, bp in _endpoint_pairs(a, b))
    distance, aport, bport = candidates[0]
    if distance <= config.ENDPOINT_TOLERANCE_MM:
        return Connection(a.id, b.id, aport, bport, "endpoint", distance,
                          "EXACT")
    return None


def detect_connections(trusses):
    connections = []
    axis_items = [item for item in trusses if item.has_axis]
    for index, a in enumerate(axis_items):
        for b in axis_items[index + 1:]:
            if a.is_line and b.is_line:
                connection = find_line_line_connection(a, b)
            else:
                connection = find_arc_connection(a, b)
            if connection:
                connections.append(connection)
    corners = [item for item in trusses if item.item_type == "Corner"]
    connections.extend(find_corner_connections(axis_items, corners))
    return connections
