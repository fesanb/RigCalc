from loadcalc import config
from loadcalc.model.construction import Connection

from .geometry import bbox_distance, distance_2d, parallel_angle_difference, point_to_segment


def _endpoint_pairs(a, b):
    return (
        ("start", a.start, "start", b.start),
        ("start", a.start, "end", b.end),
        ("end", a.end, "start", b.start),
        ("end", a.end, "end", b.end),
    )


def find_line_line_connection(a, b):
    candidates = sorted(
        (distance_2d(ap, bp), aport, bport)
        for aport, ap, bport, bp in _endpoint_pairs(a, b)
    )
    distance, aport, bport = candidates[0]
    if distance <= config.ENDPOINT_TOLERANCE_MM:
        return Connection(a.id, b.id, aport, bport, "endpoint", distance, "EXACT")

    if parallel_angle_difference(a.z_rotation_deg, b.z_rotation_deg) > config.COLLINEAR_ANGLE_TOLERANCE_DEG:
        return None

    relaxed = []
    for aport, point, other in (("start", a.start, b), ("end", a.end, b)):
        lateral, _, _, _ = point_to_segment(point, other.start, other.end)
        distances = ((distance_2d(point, other.start), "start"),
                     (distance_2d(point, other.end), "end"))
        longitudinal, bport = min(distances)
        if lateral <= config.COLLINEAR_LATERAL_TOLERANCE_MM and longitudinal <= config.COLLINEAR_LONGITUDINAL_TOLERANCE_MM:
            relaxed.append((longitudinal, aport, bport))
    for bport, point, other in (("start", b.start, a), ("end", b.end, a)):
        lateral, _, _, _ = point_to_segment(point, other.start, other.end)
        distances = ((distance_2d(point, other.start), "start"),
                     (distance_2d(point, other.end), "end"))
        longitudinal, aport = min(distances)
        if lateral <= config.COLLINEAR_LATERAL_TOLERANCE_MM and longitudinal <= config.COLLINEAR_LONGITUDINAL_TOLERANCE_MM:
            relaxed.append((longitudinal, aport, bport))
    if not relaxed:
        return None
    distance, aport, bport = sorted(relaxed)[0]
    return Connection(a.id, b.id, aport, bport, "inferred_collinear", distance, "INFERRED", distance)


def find_line_corner_connection(line, corner, line_is_a):
    if corner.bbox is None:
        return None
    candidates = sorted((bbox_distance(point, corner.bbox), port)
                        for port, point in (("start", line.start), ("end", line.end)))
    distance, port = candidates[0]
    if distance > config.CORNER_TOLERANCE_MM:
        return None
    if line_is_a:
        return Connection(line.id, corner.id, port, "corner", "line_to_corner", distance, "EXACT")
    return Connection(corner.id, line.id, "corner", port, "line_to_corner", distance, "EXACT")


def detect_connections(trusses):
    connections = []
    for index, a in enumerate(trusses):
        for b in trusses[index + 1:]:
            connection = None
            if a.is_line and b.is_line:
                connection = find_line_line_connection(a, b)
            elif a.is_line and b.item_type == "Corner":
                connection = find_line_corner_connection(a, b, True)
            elif b.is_line and a.item_type == "Corner":
                connection = find_line_corner_connection(b, a, False)
            if connection:
                connections.append(connection)
    return connections
