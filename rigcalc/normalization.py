"""Normalize Vectorworks PIO inventory into a calculation-facing contract.

This module deliberately has no dependency on the Vectorworks API.  Every
derived value retains its source field so that calculation input is auditable.
"""

import re


def parse_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][-+]?\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _value(fields, names):
    for name in names:
        value = fields.get(name)
        if value not in (None, ""):
            return name, value
    return None, None


def _kg_component(fields, label, kg_fields=(), display_fields=(), gram_fields=()):
    name, raw = _value(fields, kg_fields)
    scale = 1.0
    if name is None:
        name, raw = _value(fields, display_fields)
        # A bare internal number has unknown units.  Only accept display
        # fields when Vectorworks includes an explicit kg unit.
        if name is not None and "kg" not in str(raw).lower():
            name, raw = None, None
    if name is None:
        name, raw = _value(fields, gram_fields)
        scale = 0.001
    value = parse_number(raw)
    if value is None:
        return None
    return {
        "label": label,
        "kind": "point",
        "mass_kg": value * scale,
        "source_field": name,
        "source_value": raw,
    }


def _distributed_component(fields, total_gram_fields=(), kg_per_m_fields=(), length_fields=()):
    total_name, total_raw = _value(fields, total_gram_fields)
    rate_name, rate_raw = _value(fields, kg_per_m_fields)
    length_name, length_raw = _value(fields, length_fields)
    total, rate, length = map(parse_number, (total_raw, rate_raw, length_raw))
    if total is None and rate is None:
        return None
    return {
        "label": "distributed load",
        "kind": "distributed",
        "mass_kg": None if total is None else total / 1000.0,
        "mass_per_m_kg": rate,
        "length_mm": length,
        "source_fields": {
            "mass_kg": total_name,
            "mass_per_m_kg": rate_name,
            "length_mm": length_name,
        },
        "source_values": {
            "mass_kg": total_raw,
            "mass_per_m_kg": rate_raw,
            "length_mm": length_raw,
        },
    }


def classify(record_name, fields):
    device_type = str(fields.get("Device Type", "")).lower()
    name = record_name.lower()
    if name == "trussitem":
        return "structure"
    if name == "brxhoist":
        return "hoist"
    if name == "bridleobj":
        if (str(fields.get("AsDrop", "")).lower() == "true" and
                fields.get("BridleType") == "DeadHang"):
            return "dead_hang"
        return "bridle"
    if name == "brxcustomtrusscross":
        return "structural_link"
    if name == "light position obj":
        return "hanging_position"
    if name in ("lighting pipe", "structuralmember"):
        return "carrier"
    if "distributedweight" in name:
        return "distributed_load"
    if "weight" in name or "load" in name:
        return "load"
    if "speaker" in name or device_type == "speaker":
        return "audio"
    if "lighting device" in name or device_type == "lighting device":
        return "lighting"
    if "video" in name or "screen" in name:
        return "video"
    if "soft goods" in name:
        return "soft_goods"
    return "unknown"


def load_components(record_name, fields):
    """Extract independent mass components using explicit unit semantics."""
    if record_name == "BrxDistributedWeight":
        item = _distributed_component(fields, ("TotalWeight",), ("DistWeight",), ("Lenght", "Length"))
        return [item] if item else []
    if record_name == "BrxGenericWeight":
        item = _kg_component(fields, "generic weight", gram_fields=("Weight",))
        return [item] if item else []
    if record_name == "TrussItem":
        item = _kg_component(fields, "truss self-weight", gram_fields=("Weight",))
        return [item] if item else []
    if record_name == "BrxHoist":
        item = _kg_component(fields, "hoist and chain", gram_fields=("WeightWithChain", "HoistWt"))
        return [item] if item else []
    if record_name == "BridleObj":
        item = _kg_component(
            fields, "dead hang parts", gram_fields=("TotalWeight",))
        return [item] if item else []
    if record_name == "Speaker":
        item = _kg_component(fields, "speaker self-weight", kg_fields=("BxWeightKG",), display_fields=("BxWeight",))
        return [item] if item else []
    if record_name == "Speaker Array":
        item = _kg_component(fields, "array total weight", kg_fields=("TotalWeightKG",), display_fields=("TotalWeight",))
        return [item] if item else []
    if record_name == "Soft Goods":
        total_name, total_raw = _value(fields, ("WeightKG",))
        rate_name, rate_raw = _value(fields, ("DistWeightKG",))
        length_name, length_raw = _value(
            fields, ("AdjustableLength", "TTLSGLngthNum"))
        total, rate, length = map(
            parse_number, (total_raw, rate_raw, length_raw))
        if total is None:
            return []
        return [{
            "label": "soft goods distributed weight",
            "kind": "distributed",
            "mass_kg": total,
            "mass_per_m_kg": rate,
            "length_mm": length,
            "source_fields": {
                "mass_kg": total_name, "mass_per_m_kg": rate_name,
                "length_mm": length_name,
            },
            "source_values": {
                "mass_kg": total_raw, "mass_per_m_kg": rate_raw,
                "length_mm": length_raw,
            },
        }]
    if record_name == "Video Screen":
        screen = _kg_component(fields, "screen", kg_fields=("ScrnWeightKG",), display_fields=("ScrnWeightStr",))
        projector = _kg_component(fields, "projector", kg_fields=("ProjWeightKG",), display_fields=("ProjWeightStr",))
        return [item for item in (screen, projector) if item]
    item = _kg_component(
        fields, "object self-weight",
        kg_fields=("WeightKG", "TotalWeightKG"),
        display_fields=("Weight", "Total Weight", "TotalWeight"),
    )
    return [item] if item else []


def _connection_index(inventory):
    result = {}
    for item in inventory:
        if item.get("parametric_record") != "TrussItem":
            continue
        fields = item.get("parametric_fields", {})
        for field_name in (
            "C_START_UUID", "C_END_UUID", "C_LEFT_UUID", "C_RIGHT_UUID",
            "C_TOP_UUID", "C_BOTTOM_UUID", "C_HIGH_UUID", "C_LOW_UUID",
        ):
            uuid = fields.get(field_name)
            if uuid:
                result[uuid] = {
                    "truss_scan_id": item["scan_id"],
                    "truss_system": fields.get("TrussSystem", ""),
                    "port": field_name,
                    "layer_name": item.get("layer_name", ""),
                }
    return result


def _explicit_connections(fields, connection_index):
    references = []
    for role, names in (
        ("bottom", ("TrussSysBottom", "UUID_Bottom")),
        ("top", ("TrussSysTop", "UUID_Top", "HouseRiggingPoint1")),
    ):
        field_name, uuid = _value(fields, names)
        if uuid:
            references.append({
                "role": role,
                "source_field": field_name,
                "uuid": uuid,
                "resolved": connection_index.get(uuid),
            })
    return references


def _associations(record_name, fields):
    result = []
    if record_name == "Lighting Device" and fields.get("Position"):
        result.append({
            "kind": "hanging_position_name", "role": "member",
            "value": fields["Position"], "source_field": "Position",
        })
    if record_name == "Light Position Obj" and fields.get("Position Name"):
        result.append({
            "kind": "hanging_position_name", "role": "definition",
            "value": fields["Position Name"], "source_field": "Position Name",
        })
    return result


def normalize_inventory(inventory, included_layers=None):
    connection_index = _connection_index(inventory)
    objects = []
    included = None if included_layers is None else set(included_layers)
    for item in inventory:
        record_name = item.get("parametric_record", "")
        fields = item.get("parametric_fields", {})
        components = load_components(record_name, fields)
        explicit = _explicit_connections(fields, connection_index)
        layer_name = item.get("layer_name", "")
        in_scope = included is None or layer_name in included
        issues = []
        if not components and classify(record_name, fields) not in (
            "structural_link", "hanging_position", "carrier", "unknown"
        ):
            issues.append("no_weight_model")
        if components and not explicit and record_name != "TrussItem":
            issues.append("requires_geometric_attachment")
        if classify(record_name, fields) == "dead_hang":
            issues.append("requires_geometric_bottom_attachment")
        if item.get("parent_scan_id") and components:
            issues.append("nested_object_check_double_counting")
        if any(ref["resolved"] is None for ref in explicit):
            issues.append("unresolved_explicit_connection")
        if included is not None and any(
            ref["resolved"] is not None and
            ref["resolved"].get("layer_name") not in included
            for ref in explicit
        ):
            issues.append("connection_target_outside_scope")
        objects.append({
            "id": item.get("scan_id"),
            "record_type": record_name,
            "category": classify(record_name, fields),
            "name": fields.get("HoistName") or fields.get("Name") or fields.get("Symbol Name") or item.get("object_name", ""),
            "position_mm": item.get("position"),
            "orientation": item.get("orientation"),
            "parent_id": item.get("parent_scan_id"),
            "layer_name": layer_name,
            "scope": {
                "status": "included" if in_scope else "excluded",
                "reason": "selected_layer" if in_scope else "unselected_layer",
            },
            "load_components": components,
            "explicit_connections": explicit,
            "associations": _associations(record_name, fields),
            "nested_content_count": len(item.get("nested_content", [])),
            "issues": issues,
        })
    return {
        "schema_version": 1,
        "objects": objects,
        "summary": {
            "object_count": len(objects),
            "load_component_count": sum(len(item["load_components"]) for item in objects),
            "explicit_connection_count": sum(len(item["explicit_connections"]) for item in objects),
            "unresolved_connection_count": sum(
                1 for item in objects for ref in item["explicit_connections"] if ref["resolved"] is None
            ),
            "geometric_attachment_required_count": sum(
                "requires_geometric_attachment" in item["issues"] and
                item["scope"]["status"] == "included" for item in objects
            ),
            "included_object_count": sum(
                item["scope"]["status"] == "included" for item in objects
            ),
            "excluded_object_count": sum(
                item["scope"]["status"] == "excluded" for item in objects
            ),
        },
        "scope": {"included_layers": sorted(included or [])},
    }
