"""Read-only diagnostic inventory of Vectorworks plug-in objects."""

from .geometry import center_z, symbol_location
from .records import get_all_record_info, get_parametric_info


def _safe_call(function, *args, **kwargs):
    default = kwargs.get("default")
    try:
        return function(*args)
    except Exception:
        return default


def _child_inventory(vs, root, max_items=1000):
    """Inspect geometry nested in a Hanging Position without modifying it."""
    first_in_group = getattr(vs, "FInGroup", lambda _handle: None)
    next_object = getattr(vs, "NextObj", lambda _handle: None)
    get_definition = getattr(vs, "GetDefinition", lambda _handle: None)
    get_center = getattr(vs, "Get3DCntr", lambda _handle: None)
    get_bbox = getattr(vs, "GetBBox", lambda _handle: None)
    pending = []
    first = _safe_call(first_in_group, root)
    if first:
        pending.append((first, 0, "content"))
    definition = _safe_call(get_definition, root)
    definition_first = _safe_call(first_in_group, definition) if definition else None
    if definition_first:
        pending.append((definition_first, 0, "definition"))
    result, visited = [], set()
    while pending and len(result) < max_items:
        handle, depth, source = pending.pop()
        while handle and len(result) < max_items:
            marker = repr(handle)
            if marker in visited:
                break
            visited.add(marker)
            record_name, fields = get_parametric_info(vs, handle)
            point = symbol_location(vs, handle)
            result.append({
                "child_id": "H{:04d}".format(len(result) + 1),
                "depth": depth,
                "source": source,
                "object_type": _safe_call(vs.GetTypeN, handle),
                "object_name": _safe_call(vs.GetName, handle, default="") or "",
                "class_name": _safe_call(vs.GetClass, handle, default="") or "",
                "parametric_record": record_name or "",
                "parametric_fields": fields,
                "position": None if point is None else {
                    "x": point.x, "y": point.y, "z": center_z(vs, handle),
                },
                "center": _safe_call(get_center, handle),
                "bbox": _safe_call(get_bbox, handle),
                "orientation": _safe_call(
                    getattr(vs, "Get3DOrientation", lambda _handle: None), handle),
                "records": get_all_record_info(vs, handle),
            })
            if depth < 6:
                nested = _safe_call(first_in_group, handle)
                if nested:
                    pending.append((nested, depth + 1, "content"))
                nested_definition = _safe_call(get_definition, handle)
                nested_first = (_safe_call(first_in_group, nested_definition)
                                if nested_definition else None)
                if nested_first:
                    pending.append((nested_first, depth + 1, "definition"))
            handle = _safe_call(next_object, handle)
    return result


def _parametric_record_name(vs, handle):
    try:
        record = vs.GetParametricRecord(handle)
        return vs.GetName(record) if record else ""
    except Exception:
        return ""


def scan_plugin_inventory(vs, progress=None, detailed=True,
                          record_filter=None, included_layers=None):
    """Capture PIO identity, location and all records without changing the file."""
    handles = []
    vs.ForEachObject(handles.append, "((T=86))")
    if progress:
        progress("start", len(handles), "Leser objektinventar 0/{}".format(len(handles)))
    scan_ids = {handle: "P{:03d}".format(index) for index, handle in enumerate(handles, 1)}
    objects = []
    for index, handle in enumerate(handles, 1):
        layer_handle = _safe_call(vs.GetLayer, handle)
        layer_name = _safe_call(vs.GetLName, layer_handle, default="") if layer_handle else ""
        parametric_record = _parametric_record_name(vs, handle)
        selected = ((record_filter is None or parametric_record in record_filter) and
                    (included_layers is None or layer_name in included_layers))
        if not selected:
            if progress:
                progress("update", index, "Leser objektinventar {}/{}".format(
                    index, len(handles)))
            continue
        if not detailed:
            objects.append({
                "scan_id": "P{:03d}".format(index),
                "layer_name": layer_name or "",
                "parametric_record": parametric_record or "",
            })
            if progress:
                progress("update", index, "Leser objektinventar {}/{}".format(
                    index, len(handles)))
            continue
        _, parametric_fields = get_parametric_info(vs, handle)
        point = symbol_location(vs, handle)
        get_parent = getattr(vs, "GetParent", lambda _handle: None)
        get_orientation = getattr(vs, "Get3DOrientation", lambda _handle: None)
        parent = _safe_call(get_parent, handle)
        objects.append({
            "scan_id": "P{:03d}".format(index),
            "object_type": _safe_call(vs.GetTypeN, handle),
            "object_name": _safe_call(vs.GetName, handle, default="") or "",
            "class_name": _safe_call(vs.GetClass, handle, default="") or "",
            "layer_name": layer_name or "",
            "parent_scan_id": scan_ids.get(parent),
            "parametric_record": parametric_record or "",
            "position": None if point is None else {
                "x": point.x,
                "y": point.y,
                "z": center_z(vs, handle),
            },
            "orientation": _safe_call(get_orientation, handle),
            "parametric_fields": parametric_fields,
            "records": get_all_record_info(vs, handle),
            "nested_content": (
                _child_inventory(vs, handle)
                if parametric_record in (
                    "Light Position Obj", "BrxHoist", "BridleObj")
                else []
            ),
        })
        if progress:
            progress("update", index, "Leser objektinventar {}/{}".format(
                index, len(handles)))
    return objects
