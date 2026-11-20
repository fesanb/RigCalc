import math

from rigcalc.model import (Bridle, BridleLeg, HouseRiggingPoint,
                           DistributedLoad, DocumentModel, Point3D, PointLoad,
                           StructuralLink, Support, TrussSegment)
from rigcalc.normalization import load_components

from .geometry import (bounding_box, center_point, center_z, symbol_location,
                       z_rotation)
from .records import get_parametric_info, safe_float


def _point_with_z(point, z):
    return Point3D(point.x, point.y, z)


def _object_uuid(vs, handle):
    """Read VW's persistent object UUID without inventing an identifier."""
    try:
        value = vs.GetObjectUuid(handle)
        if isinstance(value, (tuple, list)):
            return str(value[-1]) if value and value[0] else ""
        return str(value or "")
    except Exception:
        return ""


def _record_ignored(vs, document, handle, record_name, fields):
    """Keep the ignored record name plus read-only identifying evidence."""
    document.ignored_record_types.append(record_name)
    location = symbol_location(vs, handle)
    center = center_point(vs, handle)
    document.ignored_objects.append({
        "record": record_name,
        "insertion": None if location is None else [location.x, location.y],
        "center": None if center is None else list(center),
        "fields": {str(key): str(value) for key, value in
                   (fields or {}).items()},
    })


def _parse_truss(vs, handle, object_id, fields, cable_load_kg_m=0.0,
                 safety_factor=1.0):
    location = symbol_location(vs, handle)
    if location is None:
        return None
    z = center_z(vs, handle)
    position = _point_with_z(location, z)
    length = safe_float(fields.get("Length"), 0.0)
    rotation = z_rotation(vs, handle)
    start = end = None
    if fields.get("ItemType", "") == "Line" and length > 0:
        # The longitudinal truss axis is local X. Vectorworks' Y rotation
        # supplies its elevation and Z rotation its direction in plan.
        elevation = 0.0
        try:
            orientation = vs.Get3DOrientation(handle)
            if orientation and orientation[0]:
                elevation = float(orientation[2])
                rotation = float(orientation[3])
        except Exception:
            pass
        elevation_angle = math.radians(elevation)
        plan_angle = math.radians(rotation)
        direction = (math.cos(elevation_angle) * math.cos(plan_angle),
                     math.cos(elevation_angle) * math.sin(plan_angle),
                     -math.sin(elevation_angle))
        center = center_point(vs, handle)
        if center is not None:
            # The insertion point sits at the bottom of the start face, so it
            # is off the centreline for any non-level member and its Z is not
            # the start height.  Build the axis around the 3D centre instead.
            start = Point3D(*(c - d * length / 2.0
                              for c, d in zip(center, direction)))
            end = Point3D(*(c + d * length / 2.0
                            for c, d in zip(center, direction)))
        else:
            start = position
            end = Point3D(*(c + d * length for c, d in
                            zip((position.x, position.y, position.z),
                                direction)))
    return TrussSegment(
        id=object_id, name=fields.get("Name", ""), item_type=fields.get("ItemType", ""),
        position=position, nominal_length_mm=length, start=start, end=end,
        bbox=bounding_box(vs, handle), z_rotation_deg=rotation,
        symbol=fields.get("Symbol", ""), truss_type=fields.get("Type", ""),
        corner_type=fields.get("CornerType", ""), vw_truss_system=fields.get("TrussSystem", ""),
        width_mm=safe_float(fields.get("Width"), 0.0),
        height_mm=safe_float(fields.get("Height"), 0.0),
        self_weight_kg=(safe_float(fields.get("Weight"), 0.0) /
                        1000.0 * safety_factor),
        cable_load_kg_m=max(0.0, cable_load_kg_m) * safety_factor,
        cross_section_id=fields.get("CrossSection", ""),
        vw_truss_line=fields.get("TrussSystemLineIdent", ""),
        vw_connections={name: fields.get(field, "") for name, field in (
            ("start", "C_START_UUID"), ("end", "C_END_UUID"), ("left", "C_LEFT_UUID"),
            ("right", "C_RIGHT_UUID"), ("top", "C_TOP_UUID"), ("bottom", "C_BOTTOM_UUID"),
        )},
        source_ref=handle,
    )


def _parse_lighting_pipe(vs, handle, object_id, fields, safety_factor=1.0):
    """Read a Vectorworks Lighting Pipe as a geometric carrier.

    A Lighting Pipe is often suspended directly by hoists although it does not
    participate in Spotlight's Truss System.  It remains a distinct carrier:
    no unverified Braceworks cross section is invented for it.
    """
    location = symbol_location(vs, handle)
    if location is None:
        return None
    length = safe_float(fields.get("TotalLength"), 0.0)
    if length <= 0.0:
        return None
    position = _point_with_z(location, center_z(vs, handle))
    rotation = z_rotation(vs, handle)
    angle = math.radians(rotation)
    end = Point3D(position.x + math.cos(angle)*length,
                  position.y + math.sin(angle)*length, position.z)
    diameter = safe_float(fields.get("pipeW"), 0.0)
    return TrussSegment(
        id=object_id, name=fields.get("Index") or fields.get("Name", ""),
        item_type="Lighting Pipe", position=position,
        nominal_length_mm=length, start=position, end=end,
        bbox=bounding_box(vs, handle), z_rotation_deg=rotation,
        symbol=fields.get("Pipe", ""), truss_type="Lighting Pipe",
        width_mm=diameter, height_mm=diameter,
        self_weight_kg=(safe_float(fields.get("Weight"), 0.0) / 1000.0 *
                        safety_factor),
        source_ref=handle,
    )


def _parse_support(vs, handle, object_id, fields, safety_factor=1.0):
    location = symbol_location(vs, handle)
    if location is None:
        return None
    # Use the lower rigging connection, not the hoist geometry centre.
    # Spotlight stores X/Y in Origin and the lower carrier trim separately.
    # LoadTrim (= LoHook) is the hook height at the load for both hoist
    # orientations and follows the hoist when it is moved.  TrussBottomTrim
    # is only maintained while the hoist is linked to a truss system: on an
    # unlinked hoist it keeps a stale value (in the test drawing 0 mm after
    # the rig was raised by 8 m).  A trim of 0 mm is still a real elevation,
    # so only a missing or unparseable field falls back to the next source.
    lower_source, lower_trim = None, None
    for name in ("LoadTrim", "LoHook", "TrussBottomTrim"):
        value = safe_float(fields.get(name))
        if value is not None:
            lower_source, lower_trim = name, value
            break
    if lower_trim is None:
        lower_source, lower_trim = "geometry_centre_fallback", center_z(
            vs, handle)
    position = Point3D(
        safe_float(fields.get("OriginX"), location.x),
        safe_float(fields.get("OriginY"), location.y),
        lower_trim,
    )
    geometry_field_names = (
        "HoistPos", "HoistType", "OriginX", "OriginY", "LoadTrim",
        "TrussBottomTrim", "TrussTopTrim", "HiHook", "LoHook",
        "HookToHook", "Distance_Trim_Top_Truss", "SlingHeight",
        "PickUp_InventoryName",
        "HoistSymbol_InventoryName", "SymbolUsed", "SymbolScale",
        "TrussSysBottom", "TrussSysTop",
    )
    geometry_fields = {
        name: fields.get(name, "") for name in geometry_field_names
    }
    # Include any additional pickup fields exposed by another hoist version.
    for name, value in fields.items():
        if "pickup" in name.lower() and name not in geometry_fields:
            geometry_fields[name] = value
    geometry_fields["RigCalcLowerConnectionSource"] = lower_source
    capacity_kg = safe_float(fields.get("Capacity"), 0.0) / 1000.0
    symbol = (fields.get("SymbolUsed", "") or "").replace(" ", "").lower()
    if "deadhang" in symbol:
        # A hoist object drawn with the DeadHang symbol is a fixed drop.
        # Spotlight gives it a placeholder capacity of 0.001 t (1 kg), which
        # is not a rating; leave the capacity unknown instead of reporting
        # a false overload.
        capacity_kg = 0.0
        geometry_fields["RigCalcCapacityNote"] = (
            "DeadHang symbol: placeholder capacity ignored")
    return Support(
        id=object_id, name=fields.get("HoistName", ""),
        hoist_id=fields.get("HoistID", ""), position=position,
        motor_type=fields.get("SymbolUsed", "") or fields.get("HoistName", ""),
        object_uuid=_object_uuid(vs, handle),
        capacity_raw=fields.get("Capacity", ""), vw_truss_system=fields.get("TrussSysBottom", ""),
        vw_truss_system_top=fields.get("TrussSysTop", ""),
        weight_with_chain_kg=(safe_float(
            fields.get("WeightWithChain"), 0.0) / 1000.0 * safety_factor),
        weight_with_chain_raw_kg=(safe_float(
            fields.get("WeightWithChain"), 0.0) / 1000.0),
        manual_load_kg=(safe_float(
            fields.get("RoofForceNoDeadloadWeight"), 0.0) / 1000.0 *
                        safety_factor),
        manual_load_raw_kg=(safe_float(
            fields.get("RoofForceNoDeadloadWeight"), 0.0) / 1000.0),
        capacity_kg=capacity_kg,
        object_position=Point3D(location.x, location.y, center_z(vs, handle)),
        geometry_fields=geometry_fields,
        source_ref=handle,
    )


def _parse_dead_hang(vs, handle, object_id, fields, safety_factor=1.0):
    """Convert a one-leg DeadHang Drop into a tension-only support link.

    Vectorworks stores the lower load point at ApexHeight - DropLength and
    identifies the upper carrier with HouseRiggingPoint1. Other bridle types
    remain unresolved until their multi-leg force distribution is modelled.
    """
    if (str(fields.get("AsDrop", "")).lower() != "true" or
            fields.get("BridleType", "") != "DeadHang" or
            not fields.get("HouseRiggingPoint1", "")):
        return None
    location = symbol_location(vs, handle)
    x = safe_float(fields.get("RelativeDimX"),
                   location.x if location else 0.0)
    y = safe_float(fields.get("RelativeDimY"),
                   location.y if location else 0.0)
    apex_z = safe_float(fields.get("ApexHeight"), 0.0)
    drop_length = safe_float(fields.get("DropLength"), 0.0)
    top_z = safe_float(fields.get("TrimmLeg1"), apex_z)
    geometry_field_names = (
        "AsDrop", "BridleType", "ApexHeight", "DropLength",
        "RelativeDimX", "RelativeDimY", "TrimmLeg1", "LengthLeg1",
        "BuiledLengthLeg1", "AngleLeg1", "HouseRiggingPoint1",
        "ConnectedHoistUUID", "TotalWeight", "CalculateWeightFromParts",
        "ForceDownLegMax",
    )
    return Support(
        id=object_id, name=fields.get("Name", "") or "DeadHang",
        position=Point3D(x, y, apex_z - drop_length),
        capacity_raw=fields.get("ForceDownLegMax", ""),
        vw_truss_system_top=fields.get("HouseRiggingPoint1", ""),
        weight_with_chain_kg=(
            safe_float(fields.get("TotalWeight"), 0.0) /
            1000.0 * safety_factor),
        capacity_kg=(
            safe_float(fields.get("ForceDownLegMax"), 0.0) / 9.80665),
        is_structural_link=True,
        object_position=(Point3D(location.x, location.y, center_z(vs, handle))
                         if location else None),
        geometry_fields={
            name: fields.get(name, "") for name in geometry_field_names},
        support_kind="dead_hang",
        transfer_target_position=Point3D(x, y, top_z),
        source_ref=handle,
    )


BRIDLE_LEG_COUNTS = {"twoway": 2, "threeway": 3, "fourway": 4}


def _parse_bridle(vs, handle, object_id, fields, safety_factor=1.0):
    """Read a multi-leg bridle (apex, legs and Vectorworks leg results).

    Lengths and trims are mm, ``TotalWeight`` is grams and ``ForceLeg*`` /
    ``ForceMaxLeg*`` are N (leg force x sin(angle) equals the vertical force
    on the connected HouseRiggingPoint in the test drawing).
    """
    bridle_type = str(fields.get("BridleType", ""))
    count = BRIDLE_LEG_COUNTS.get(bridle_type.replace(" ", "").lower())
    if count is None:
        return None
    location = symbol_location(vs, handle)
    x = safe_float(fields.get("RelativeDimX"), location.x if location else None)
    y = safe_float(fields.get("RelativeDimY"), location.y if location else None)
    apex_z = safe_float(fields.get("ApexHeight"))
    if x is None or y is None or apex_z is None:
        return None
    legs = []
    for number in range(1, count+1):
        length = safe_float(fields.get("LengthLeg{}".format(number)))
        trim = safe_float(fields.get("TrimmLeg{}".format(number)))
        if not length or trim is None:
            return None
        legs.append(BridleLeg(
            number=number, length_mm=length, trim_mm=trim,
            angle_deg=safe_float(fields.get("AngleLeg{}".format(number))),
            vw_force_n=safe_float(fields.get("ForceLeg{}".format(number))),
            max_force_n=safe_float(fields.get("ForceMaxLeg{}".format(number)))))
    weight_raw = safe_float(fields.get("TotalWeight"), 0.0)/1000.0
    return Bridle(
        id=object_id, name=fields.get("Name", ""),
        index=fields.get("Index", ""), bridle_type=bridle_type,
        apex=Point3D(x, y, apex_z),
        connected_hoist_uuid=str(fields.get("ConnectedHoistUUID", "")),
        weight_kg=weight_raw*safety_factor, weight_raw_kg=weight_raw,
        legs=legs,
        down_leg_max_force_n=safe_float(fields.get("ForceDownLegMax")),
        vw_inventory=_bridle_inventory(vs, handle),
        object_uuid=_object_uuid(vs, handle), source_ref=handle)


def _bridle_inventory(vs, handle):
    """All records and nested objects of a bridle (read only, bounded)."""
    from .inventory import _child_inventory
    from .records import get_all_record_info
    try:
        records = get_all_record_info(vs, handle)
    except Exception as error:  # noqa: BLE001 - evidence only
        records = {"error": str(error)}
    try:
        children = _child_inventory(vs, handle, max_items=200)
    except Exception as error:  # noqa: BLE001 - evidence only
        children = [{"error": str(error)}]
    return {"records": records, "children": children}


def _parse_house_rigging_point(vs, handle, object_id, fields):
    location = symbol_location(vs, handle)
    center = center_point(vs, handle)
    if location is None and center is None:
        return None
    x = safe_float(fields.get("OriginX"), location.x if location else center[0])
    y = safe_float(fields.get("OriginY"), location.y if location else center[1])
    z = center[2] if center is not None else 0.0

    def triple(prefix):
        values = [safe_float(fields.get(prefix+axis)) for axis in "XYZ"]
        return None if any(value is None for value in values) else tuple(values)

    return HouseRiggingPoint(
        id=object_id, position=Point3D(x, y, z),
        object_uuid=_object_uuid(vs, handle),
        vw_force_n=triple("Force"), max_force_n=triple("MaxForce"),
        source_ref=handle)


def _parse_load(vs, handle, object_id, record_name, fields):
    location = symbol_location(vs, handle)
    if location is None:
        return None
    if record_name == "Soft Goods":
        # The generic object Z is the curtain geometry centre, not its
        # suspension line. Loads must attach at the top trim.
        attachment_z = safe_float(
            fields.get("TopTrim", fields.get("Top Trim")),
            center_z(vs, handle))
    else:
        attachment_z = safe_float(
            fields.get("Z Location"), center_z(vs, handle))
    position = Point3D(
        safe_float(fields.get("X Location"), location.x),
        safe_float(fields.get("Y Location"), location.y),
        attachment_z,
    )
    weight_raw = next((fields[name] for name in (
        "Weight", "Total Weight", "Load", "WeightDouble") if name in fields), None)
    return PointLoad(
        id=object_id, record_type=record_name,
        name=(fields.get("FixtureID") or fields.get("Name") or
              fields.get("LoadName") or fields.get("Load Name") or ""),
        position=position, weight_raw=weight_raw,
        weight_kg=safe_float(weight_raw), raw_fields=fields,
        source_ref=handle,
    )


def _parse_normalized_loads(vs, handle, object_id, record_name, fields,
                            safety_factor=1.0):
    base = _parse_load(vs, handle, object_id, record_name, fields)
    if base is None:
        return [], []
    points, distributed = [], []
    components = load_components(record_name, fields)
    for index, component in enumerate(components, 1):
        if component["kind"] == "point" and component.get("mass_kg") is not None:
            points.append(PointLoad(
                id=object_id if index == 1 else "{}_{}".format(object_id, index),
                record_type=record_name,
                name="{}{}".format(
                    base.name,
                    " - " + component["label"] if len(components) > 1 else ""),
                position=base.position, weight_raw=component.get("source_value"),
                weight_kg=component["mass_kg"] * safety_factor,
                unfactored_weight_kg=component["mass_kg"],
                raw_fields=fields,
                source_ref=handle,
            ))
        elif component["kind"] == "distributed":
            length_mm = component.get("length_mm")
            end_position = None
            if length_mm is not None:
                elevation, rotation = 0.0, z_rotation(vs, handle)
                try:
                    orientation = vs.Get3DOrientation(handle)
                    if orientation and orientation[0]:
                        elevation, rotation = (float(orientation[2]),
                                               float(orientation[3]))
                except Exception:
                    pass
                elevation, rotation = (math.radians(elevation),
                                       math.radians(rotation))
                horizontal = math.cos(elevation) * length_mm
                end_position = Point3D(
                    base.position.x + math.cos(rotation) * horizontal,
                    base.position.y + math.sin(rotation) * horizontal,
                    base.position.z - math.sin(elevation) * length_mm)
            distributed.append(DistributedLoad(
                id=object_id, name=base.name, position=base.position,
                record_type=record_name,
                total_mass_kg=(component.get("mass_kg") * safety_factor
                               if component.get("mass_kg") is not None
                               else None),
                mass_per_m_kg=(component.get("mass_per_m_kg") * safety_factor
                               if component.get("mass_per_m_kg") is not None
                               else None),
                length_mm=length_mm, end_position=end_position, raw_fields=fields,
                source_ref=handle,
            ))
    return points, distributed


def _suppress_speaker_array_members(document):
    arrays = [item for item in document.point_loads
              if item.record_type == "Speaker Array"]
    speakers = [item for item in document.point_loads
                if item.record_type == "Speaker"]
    suppressed = set()
    for array in arrays:
        candidates = []
        for speaker in speakers:
            if speaker.id in suppressed:
                continue
            distance = math.sqrt(
                (speaker.position.x - array.position.x) ** 2 +
                (speaker.position.y - array.position.y) ** 2 +
                (speaker.position.z - array.position.z) ** 2)
            if distance <= 1000.0 and speaker.weight_kg is not None:
                candidates.append((distance, speaker.id, speaker))
        included_mass = 0.0
        for _, _, speaker in sorted(candidates):
            if included_mass + speaker.weight_kg <= (array.weight_kg or 0.0) + 0.01:
                included_mass += speaker.weight_kg
                suppressed.add(speaker.id)
                document.suppressed_point_loads.append(speaker)
    if suppressed:
        document.point_loads = [
            item for item in document.point_loads if item.id not in suppressed]


def _object_layer_name(vs, handle):
    try:
        layer = vs.GetLayer(handle)
        return vs.GetLName(layer) if layer else ""
    except Exception:
        return ""


def scan_document(vs_module=None, included_layers=None, progress=None,
                  cable_load_kg_m=0.0, safety_factor=1.0):
    if vs_module is None:
        import vs as vs_module
    handles = []
    vs_module.ForEachObject(handles.append, "((T=86))")
    if progress:
        progress("start", len(handles), "Scanning model 0/{}".format(len(handles)))
    document = DocumentModel()
    for counter, handle in enumerate(handles, 1):
        if included_layers is not None and _object_layer_name(vs_module, handle) not in included_layers:
            if progress:
                progress("update", counter, "Scanning model {}/{}".format(
                    counter, len(handles)))
            continue
        record_name, fields = get_parametric_info(vs_module, handle)
        if not record_name:
            if progress:
                progress("update", counter, "Scanning model {}/{}".format(
                    counter, len(handles)))
            continue
        if record_name == "TrussItem":
            item = _parse_truss(
                vs_module, handle, "T{:03d}".format(counter), fields,
                cable_load_kg_m=cable_load_kg_m,
                safety_factor=safety_factor)
            if item:
                document.trusses.append(item)
        elif record_name == "Lighting Pipe":
            item = _parse_lighting_pipe(
                vs_module, handle, "P{:03d}".format(counter), fields,
                safety_factor=safety_factor)
            if item:
                document.trusses.append(item)
        elif record_name == "BrxHoist":
            item = _parse_support(
                vs_module, handle, "H{:03d}".format(counter), fields,
                safety_factor=safety_factor)
            if item:
                document.supports.append(item)
        elif record_name == "BridleObj":
            item = _parse_dead_hang(
                vs_module, handle, "D{:03d}".format(counter), fields,
                safety_factor=safety_factor)
            bridle = None if item else _parse_bridle(
                vs_module, handle, "B{:03d}".format(counter), fields,
                safety_factor=safety_factor)
            if item:
                document.supports.append(item)
            elif bridle:
                document.bridles.append(bridle)
            else:
                _record_ignored(vs_module, document, handle, record_name, fields)
        elif record_name == "HouseRiggingPoint":
            point = _parse_house_rigging_point(
                vs_module, handle, "R{:03d}".format(counter), fields)
            if point:
                document.house_rigging_points.append(point)
            else:
                _record_ignored(vs_module, document, handle, record_name, fields)
        elif record_name == "BrxCustomTrussCross":
            location = symbol_location(vs_module, handle)
            if location:
                document.structural_links.append(StructuralLink(
                    id="X{:03d}".format(counter), name=fields.get("Name", ""),
                    position=Point3D(location.x, location.y, center_z(vs_module, handle)),
                    top_uuid=fields.get("UUID_Top", ""),
                    bottom_uuid=fields.get("UUID_Bottom", ""),
                    source_ref=handle,
                ))
        else:
            points, distributed = _parse_normalized_loads(
                vs_module, handle, "L{:03d}".format(counter), record_name,
                fields, safety_factor=safety_factor)
            if points or distributed:
                document.point_loads.extend(points)
                document.distributed_loads.extend(distributed)
            else:
                _record_ignored(vs_module, document, handle, record_name, fields)
        if progress:
            progress("update", counter, "Scanning model {}/{}".format(
                counter, len(handles)))
    _suppress_speaker_array_members(document)
    return document
