from rigcalc import config
from rigcalc.model.construction import AttachedObject, Attachment

from .geometry import point_to_segment


def nearest_line_truss(position, trusses):
    best = None
    for truss in trusses:
        if not truss.is_line:
            continue
        distance, local_t, qx, qy = point_to_segment(position, truss.start, truss.end)
        candidate = (distance, truss.id, truss, local_t, qx, qy)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    return best


def attach_item(item, construction):
    nearest = nearest_line_truss(item.position, construction.truss_segments)
    if nearest is None:
        return None
    distance, _, truss, local_t, qx, qy = nearest
    local = local_t * truss.geometric_length_mm
    station = None
    station_range = construction.station_map.get(truss.id)
    if station_range:
        if station_range.direction == "forward":
            station = station_range.start_station_mm + local
        elif station_range.direction == "reverse":
            station = station_range.end_station_mm - local
    return AttachedObject(item, Attachment(
        truss.id, truss.name, distance, local, station, qx, qy,
        distance > config.ATTACHMENT_WARNING_DISTANCE_MM,
    ))


def attach_document_objects(document, constructions):
    for attribute, objects in (("supports", document.supports), ("point_loads", document.point_loads)):
        for item in objects:
            candidates = []
            for construction in constructions:
                attached = attach_item(item, construction)
                if attached:
                    candidates.append((attached.attachment.distance_from_truss_axis_mm, construction.id, construction, attached))
            if candidates:
                _, _, construction, attached = min(candidates, key=lambda value: value[:2])
                getattr(construction, attribute).append(attached)
