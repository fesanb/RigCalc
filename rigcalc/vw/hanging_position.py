"""Convert readable Hanging Position contents into global truss segments."""

import math

from rigcalc.model import Point3D, TrussSegment

from .records import safe_float


def _geometry_key(item):
    position = item.get("position") or {}
    orientation = item.get("orientation") or (False, 0, 0, 0)
    fields = item.get("parametric_fields", {})
    return (
        round(float(position.get("x", 0.0)), 1),
        round(float(position.get("y", 0.0)), 1),
        round(float(position.get("z", 0.0)), 1),
        round(float(orientation[2] if len(orientation) > 2 else 0.0), 3),
        round(float(orientation[3] if len(orientation) > 3 else 0.0), 3),
        round(safe_float(fields.get("Length"), 0.0), 1),
        fields.get("Name", ""),
    )


def extract_hanging_position_trusses(inventory, included_layers):
    included = set(included_layers or [])
    result = []
    for position_object in inventory:
        if (position_object.get("parametric_record") != "Light Position Obj" or
                position_object.get("layer_name") not in included):
            continue
        root = position_object.get("position") or {}
        root_orientation = position_object.get("orientation") or (False, 0, 0, 0)
        root_plan_deg = float(
            root_orientation[3] if len(root_orientation) > 3 else 0.0)
        root_plan = math.radians(root_plan_deg)
        position_fields = position_object.get("parametric_fields", {})
        position_name = position_fields.get("Position Name", "")
        seen = set()
        counter = 0
        for child in position_object.get("nested_content", []):
            if child.get("parametric_record") != "TrussItem":
                continue
            key = _geometry_key(child)
            if key in seen:
                continue
            seen.add(key)
            counter += 1
            fields = child.get("parametric_fields", {})
            local = child.get("position") or {}
            lx, ly = float(local.get("x", 0.0)), float(local.get("y", 0.0))
            start = Point3D(
                float(root.get("x", 0.0)) + lx * math.cos(root_plan) - ly * math.sin(root_plan),
                float(root.get("y", 0.0)) + lx * math.sin(root_plan) + ly * math.cos(root_plan),
                float(local.get("z", 0.0)),
            )
            orientation = child.get("orientation") or (False, 0, 0, 0)
            elevation_deg = float(orientation[2] if len(orientation) > 2 else 0.0)
            child_plan_deg = float(orientation[3] if len(orientation) > 3 else 0.0)
            plan_deg = root_plan_deg + child_plan_deg
            length = safe_float(fields.get("Length"), 0.0)
            elevation = math.radians(elevation_deg)
            plan = math.radians(plan_deg)
            horizontal = math.cos(elevation) * length
            end = Point3D(
                start.x + math.cos(plan) * horizontal,
                start.y + math.sin(plan) * horizontal,
                start.z - math.sin(elevation) * length,
            )
            result.append(TrussSegment(
                id="HP{}_T{:03d}".format(position_object["scan_id"][1:], counter),
                name=fields.get("Name", ""), item_type=fields.get("ItemType", ""),
                position=start, nominal_length_mm=length, start=start, end=end,
                z_rotation_deg=plan_deg, symbol=fields.get("Symbol", ""),
                truss_type=fields.get("Type", ""),
                corner_type=fields.get("CornerType", ""),
                width_mm=safe_float(fields.get("Width"), 0.0),
                height_mm=safe_float(fields.get("Height"), 0.0),
                self_weight_kg=safe_float(fields.get("Weight"), 0.0) / 1000.0,
                cross_section_id=fields.get("CrossSection", ""),
                vw_truss_system="HP:{}".format(position_object["scan_id"]),
                vw_truss_line=fields.get("TrussSystemLineIdent", ""),
                source_position_name=position_name,
                vw_connections={},
            ))
    return result
