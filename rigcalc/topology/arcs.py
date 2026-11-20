"""Resolve curved (Circle) truss items to centreline arcs.

Vectorworks exposes a Circle segment's insertion point, plan rotation,
nominal (arc) length, width and symbol name, but no start/end chord.  For the
Spotlight circle symbols in use the insertion point is the arc start on the
truss centreline, the rotation is the outward radial direction there, and the
symbol name carries the outer radius (for example ``R4000``).  The centreline
radius is that radius minus half the truss width.

The resolved arc is accepted only when it is independently consistent with
the item's 2D bounding box when that box is plan-consistent (it contains
the insertion point).  The box is view-dependent, so without it the observed
Spotlight convention is used and recorded as the arc ``source``.
"""

import re
from math import cos, pi, radians, sin

SYMBOL_RADIUS = re.compile(r"\bR\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
BBOX_TOLERANCE_MM = 25.0


def _symbol_radius(truss):
    for text in (truss.symbol, truss.name):
        match = SYMBOL_RADIUS.search(text or "")
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _arc_points(center_x, center_y, radius, start, sweep, count=24):
    return [(center_x+radius*cos(start+sweep*index/count),
             center_y+radius*sin(start+sweep*index/count))
            for index in range(count+1)]


def _bbox_fit(points, bbox, half_width):
    """Largest distance a centreline point lies outside the bbox (mm)."""
    x1, x2 = sorted((bbox.first.x, bbox.second.x))
    y1, y2 = sorted((bbox.first.y, bbox.second.y))
    worst = 0.0
    for x, y in points:
        dx = max(x1+half_width-x, 0.0, x-(x2-half_width))
        dy = max(y1+half_width-y, 0.0, y-(y2-half_width))
        worst = max(worst, dx, dy)
    return worst


def resolve_circle_arc(truss):
    """Return the centreline arc dict, or None when it cannot be proven."""
    if truss.item_type != "Circle" or truss.bbox is None:
        return None
    outer = _symbol_radius(truss)
    length = truss.nominal_length_mm
    if not outer or not length or length <= 0.0:
        return None
    half_width = max(truss.width_mm, truss.height_mm, 0.0)/2.0
    angle = radians(truss.z_rotation_deg)
    centreline = outer-half_width
    if centreline <= 0.0 or length/centreline > 2.0*pi+1.0e-6:
        return None
    if truss.bbox is not None and _bbox_contains(truss.bbox, truss.position,
                                                 half_width):
        fitted = _fit_to_bbox(truss, outer, half_width, angle, length)
        if fitted is not None:
            return fitted
    # The 2D bounding box is view-dependent (a 3D view returns projected
    # screen coordinates).  Without a plan-consistent box, use the
    # Spotlight circle convention observed for these symbols: centreline
    # radius, counter-clockwise sweep from the insertion point.
    return _arc(truss, centreline, angle, length/centreline,
                "symbol_convention_centreline_ccw")


def _bbox_contains(bbox, point, margin):
    x1, x2 = sorted((bbox.first.x, bbox.second.x))
    y1, y2 = sorted((bbox.first.y, bbox.second.y))
    return (x1-margin <= point.x <= x2+margin and
            y1-margin <= point.y <= y2+margin)


def _arc(truss, radius, angle, sweep, source):
    return {
        "center_x": truss.position.x-radius*cos(angle),
        "center_y": truss.position.y-radius*sin(angle),
        "z": truss.position.z, "radius_mm": radius,
        "start_angle_rad": angle, "sweep_rad": sweep, "source": source,
    }


def _fit_to_bbox(truss, outer, half_width, angle, length):
    candidates = []
    for radius in (outer-half_width, outer):
        if radius <= 0.0 or length/radius > 2.0*pi+1.0e-6:
            continue
        for direction in (1.0, -1.0):
            arc = _arc(truss, radius, angle, direction*length/radius,
                       "plan_bounding_box_fit")
            misfit = _bbox_fit(_arc_points(
                arc["center_x"], arc["center_y"], radius, angle,
                arc["sweep_rad"]), truss.bbox, half_width)
            candidates.append((misfit, radius, direction, arc))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    best = candidates[0]
    if best[0] > BBOX_TOLERANCE_MM+half_width:
        return None
    for other in candidates[1:]:
        if (other[0] <= best[0]+1.0 and
                (abs(other[1]-best[1]) > 1.0 or other[2] != best[2])):
            return None
    return best[3]


def resolve_document_arcs(trusses):
    """Attach centreline arcs and endpoints to resolvable Circle items."""
    point_type = None
    for truss in trusses:
        if truss.item_type != "Circle" or truss.arc is not None:
            continue
        arc = resolve_circle_arc(truss)
        if arc is None:
            continue
        point_type = type(truss.position)
        truss.arc = arc
        end_angle = arc["start_angle_rad"]+arc["sweep_rad"]
        truss.start = point_type(
            arc["center_x"]+arc["radius_mm"]*cos(arc["start_angle_rad"]),
            arc["center_y"]+arc["radius_mm"]*sin(arc["start_angle_rad"]),
            arc["z"])
        truss.end = point_type(
            arc["center_x"]+arc["radius_mm"]*cos(end_angle),
            arc["center_y"]+arc["radius_mm"]*sin(end_angle), arc["z"])
