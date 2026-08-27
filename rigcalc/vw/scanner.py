import math

from rigcalc.model import DocumentModel, Point3D, PointLoad, Support, TrussSegment

from .geometry import bounding_box, center_z, symbol_location, z_rotation
from .records import get_parametric_info, safe_float


def _point_with_z(point, z):
    return Point3D(point.x, point.y, z)


def _parse_truss(vs, handle, object_id, fields):
    location = symbol_location(vs, handle)
    if location is None:
        return None
    z = center_z(vs, handle)
    position = _point_with_z(location, z)
    length = safe_float(fields.get("Length"), 0.0)
    rotation = z_rotation(vs, handle)
    start = end = None
    if fields.get("ItemType", "") == "Line" and length > 0:
        angle = math.radians(rotation)
        start = position
        end = Point3D(position.x + math.cos(angle) * length,
                      position.y + math.sin(angle) * length, z)
    return TrussSegment(
        id=object_id, name=fields.get("Name", ""), item_type=fields.get("ItemType", ""),
        position=position, nominal_length_mm=length, start=start, end=end,
        bbox=bounding_box(vs, handle), z_rotation_deg=rotation,
        symbol=fields.get("Symbol", ""), truss_type=fields.get("Type", ""),
        corner_type=fields.get("CornerType", ""), vw_truss_system=fields.get("TrussSystem", ""),
        vw_truss_line=fields.get("TrussSystemLineIdent", ""),
        vw_connections={name: fields.get(field, "") for name, field in (
            ("start", "C_START_UUID"), ("end", "C_END_UUID"), ("left", "C_LEFT_UUID"),
            ("right", "C_RIGHT_UUID"), ("top", "C_TOP_UUID"), ("bottom", "C_BOTTOM_UUID"),
        )},
        source_ref=handle,
    )


def _parse_support(vs, handle, object_id, fields):
    location = symbol_location(vs, handle)
    if location is None:
        return None
    return Support(
        id=object_id, name=fields.get("HoistName", ""),
        hoist_id=fields.get("HoistID", ""), position=_point_with_z(location, center_z(vs, handle)),
        capacity_raw=fields.get("Capacity", ""), vw_truss_system=fields.get("TrussSysBottom", ""),
        source_ref=handle,
    )


def _parse_load(vs, handle, object_id, record_name, fields):
    location = symbol_location(vs, handle)
    if location is None:
        return None
    position = Point3D(
        safe_float(fields.get("X Location"), location.x),
        safe_float(fields.get("Y Location"), location.y),
        safe_float(fields.get("Z Location"), center_z(vs, handle)),
    )
    weight_raw = next((fields[name] for name in ("Weight", "Total Weight", "Load", "WeightDouble") if name in fields), None)
    # Native Spotlight load record names vary by version; retain all fields and
    # parse the common weight names without requiring a formal association.
    weight_kg = safe_float(weight_raw)
    return PointLoad(
        id=object_id, record_type=record_name,
        name=(fields.get("FixtureID") or fields.get("Name") or fields.get("LoadName") or fields.get("Load Name") or ""),
        position=position, weight_raw=weight_raw, weight_kg=weight_kg,
        raw_fields=fields, source_ref=handle,
    )


def scan_document(vs_module=None):
    if vs_module is None:
        import vs as vs_module
    handles = []
    vs_module.ForEachObject(handles.append, "((T=86))")
    document = DocumentModel()
    for counter, handle in enumerate(handles, 1):
        record_name, fields = get_parametric_info(vs_module, handle)
        if not record_name:
            continue
        if record_name == "TrussItem":
            item = _parse_truss(vs_module, handle, "T{:03d}".format(counter), fields)
            if item:
                document.trusses.append(item)
        elif record_name == "BrxHoist":
            item = _parse_support(vs_module, handle, "H{:03d}".format(counter), fields)
            if item:
                document.supports.append(item)
        elif record_name == "Lighting Device" or "load" in record_name.lower():
            item = _parse_load(vs_module, handle, "L{:03d}".format(counter), record_name, fields)
            if item:
                document.point_loads.append(item)
        else:
            document.ignored_record_types.append(record_name)
    return document
