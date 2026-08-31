"""Geometry reduction for planar inclined truss-chain analysis."""

from math import hypot


PLANAR_LATERAL_TOLERANCE_MM = 1.0


def inclined_station_coordinates(construction):
    """Return station-to-(horizontal,z) coordinates for one vertical plane.

    The future inclined adapter can use this reduction while retaining global
    vertical gravity.  Horizontal turns are deliberately rejected: they are a
    true 3D load-path problem, not an inclined planar beam.
    """
    spans = [construction.station_map[identifier]
             for identifier in construction.ordered_truss_ids
             if identifier in construction.station_map]
    trusses = {item.id: item for item in construction.truss_segments}
    ordered = [trusses[identifier] for identifier in construction.ordered_truss_ids
               if identifier in trusses]
    if not ordered or not spans:
        return None, "missing_ordered_inclined_geometry"
    origin = ordered[0].start
    direction = None
    for truss in ordered:
        dx, dy = truss.end.x-truss.start.x, truss.end.y-truss.start.y
        length = hypot(dx, dy)
        if length > PLANAR_LATERAL_TOLERANCE_MM:
            direction = (dx/length, dy/length)
            break
    if direction is None:
        return None, "unsupported_vertical_truss_geometry"
    coordinates = {}
    for truss, span in zip(ordered, spans):
        for station, point in ((span.start_station_mm, truss.start),
                               (span.end_station_mm, truss.end)):
            dx, dy = point.x-origin.x, point.y-origin.y
            horizontal = dx*direction[0]+dy*direction[1]
            lateral = abs(dx*direction[1]-dy*direction[0])
            if lateral > PLANAR_LATERAL_TOLERANCE_MM:
                return None, "unsupported_nonplanar_horizontal_turn:{}".format(
                    truss.id)
            coordinates[round(station, 6)] = (horizontal, point.z)
    return coordinates, None


def horizontal_coordinate(station_mm, coordinates):
    """Linearly interpolate planar horizontal coordinate at a station."""
    points = sorted(coordinates.items())
    for (start, start_value), (end, end_value) in zip(points, points[1:]):
        if start <= station_mm <= end and end > start:
            fraction = (station_mm-start)/(end-start)
            return start_value[0]+fraction*(end_value[0]-start_value[0])
    return coordinates.get(round(station_mm, 6), (None, None))[0]


def planar_coordinate(station_mm, coordinates):
    points = sorted(coordinates.items())
    for (start, first), (end, second) in zip(points, points[1:]):
        if start <= station_mm <= end and end > start:
            fraction = (station_mm-start)/(end-start)
            return tuple(a+fraction*(b-a) for a, b in zip(first, second))
    return coordinates.get(round(station_mm, 6), (None, None))
