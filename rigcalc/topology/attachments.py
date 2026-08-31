from dataclasses import replace
from math import radians, sin

from rigcalc import config
from rigcalc.model.construction import AttachedObject, Attachment
from rigcalc.model.hoist import Support

from .geometry import point_to_segment, point_to_segment_2d


def nearest_line_truss(position, trusses, plan_only=False):
    best = None
    for truss in trusses:
        if not truss.is_line:
            continue
        if plan_only:
            axis_distance, local_t, qx, qy = point_to_segment_2d(
                position, truss.start, truss.end)
            qz = truss.start.z + local_t * (truss.end.z - truss.start.z)
        else:
            axis_distance, local_t, qx, qy, qz = point_to_segment(
                position, truss.start, truss.end)
        envelope_radius = max(truss.width_mm, truss.height_mm) / 2.0
        clearance = max(0.0, axis_distance - envelope_radius)
        candidate = (
            clearance, axis_distance, truss.id, truss, local_t, qx, qy, qz)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    return best


def attach_item(item, construction, plan_only=False, method="geometry_sphere"):
    nearest = nearest_line_truss(
        item.position, construction.truss_segments, plan_only=plan_only)
    if nearest is None:
        return None
    clearance, axis_distance, _, truss, local_t, qx, qy, qz = nearest
    if clearance > config.ATTACHMENT_SEARCH_RADIUS_MM:
        return None
    local = local_t * truss.geometric_length_mm
    station = None
    station_range = construction.station_map.get(truss.id)
    if station_range:
        if station_range.direction == "forward":
            station = station_range.start_station_mm + local
        elif station_range.direction == "reverse":
            station = station_range.end_station_mm - local
    return AttachedObject(item, Attachment(
        truss_id=truss.id,
        truss_name=truss.name,
        distance_from_truss_axis_mm=axis_distance,
        local_position_from_truss_start_mm=local,
        global_station_mm=station,
        projected_x=qx,
        projected_y=qy,
        projected_z=qz,
        warning=clearance > config.ATTACHMENT_EXACT_DISTANCE_MM,
        method=method,
        confidence=("EXACT" if clearance <= config.ATTACHMENT_EXACT_DISTANCE_MM
                    else "INFERRED"),
        carrier_clearance_mm=clearance,
    ))


def _explicit_support_attachment(support, constructions):
    uuid = support.vw_truss_system
    if not uuid:
        return None
    matched_constructions = []
    for construction in constructions:
        for truss in construction.truss_segments:
            if uuid in truss.vw_connections.values():
                matched_constructions.append(construction)
                break
    candidates = []
    for construction in matched_constructions:
        attached = attach_item(
            support, construction, plan_only=False,
            method="explicit_system_3d_geometry")
        if attached:
            candidates.append((
                attached.attachment.carrier_clearance_mm,
                attached.attachment.distance_from_truss_axis_mm,
                construction.id, construction, attached))
            continue

        # VW's scalar TrussBottomTrim is a horizontal-Z convention.  It does
        # not describe the hook point on a strongly inclined truss.  In that
        # specific case an explicit TrussSysBottom UUID plus a close plan
        # projection is independent, high-confidence evidence.  Horizontal
        # carriers still require the normal full 3D check above.
        plan_attached = attach_item(
            support, construction, plan_only=True,
            method="explicit_system_inclined_plan_geometry")
        if plan_attached:
            carrier = next(
                (item for item in construction.truss_segments
                 if item.id == plan_attached.attachment.truss_id), None)
            minimum_vertical_change = (
                carrier.geometric_length_mm*sin(radians(5.0))
                if carrier is not None else float("inf"))
            if (carrier is not None and
                    abs(carrier.end.z-carrier.start.z) >=
                    minimum_vertical_change):
                plan_attached.attachment.confidence = "EXACT"
                candidates.append((
                    plan_attached.attachment.carrier_clearance_mm,
                    plan_attached.attachment.distance_from_truss_axis_mm,
                    construction.id, construction, plan_attached))
    if not candidates:
        return None
    _, _, _, construction, attached = min(candidates, key=lambda value: value[:3])
    return construction, attached


def _construction_for_uuid(uuid, constructions):
    if not uuid:
        return None
    for construction in constructions:
        for truss in construction.truss_segments:
            if uuid in truss.vw_connections.values():
                return construction
    return None


def _unresolved_explicit_inclined_attachment(support, constructions):
    """Use unique, exact plan geometry when VW's stored UUID is stale.

    This is deliberately limited to hoists carrying a non-empty but unresolved
    TrussSysBottom value and carriers inclined by at least five degrees.  It
    addresses VW's flat trim convention without enabling general plan-only
    attachment.
    """
    if not support.vw_truss_system:
        return None
    candidates = []
    for construction in constructions:
        attached = attach_item(
            support, construction, plan_only=True,
            method="unresolved_system_inclined_plan_geometry")
        if attached is None:
            continue
        carrier = next(
            (item for item in construction.truss_segments
             if item.id == attached.attachment.truss_id), None)
        if carrier is None:
            continue
        minimum_vertical_change = (
            carrier.geometric_length_mm*sin(radians(5.0)))
        if (abs(carrier.end.z-carrier.start.z) < minimum_vertical_change or
                attached.attachment.carrier_clearance_mm >
                config.ATTACHMENT_EXACT_DISTANCE_MM):
            continue
        candidates.append((construction, attached))
    # A plan crossing at two different elevations is ambiguous and must not be
    # resolved by proximity alone.
    if len(candidates) != 1:
        return None
    construction, attached = candidates[0]
    attached.attachment.confidence = "INFERRED"
    return construction, attached


def _missing_identifier_inclined_attachment(support, constructions):
    """Diagnostic-only fallback for a uniquely exact plan hit on an incline."""
    if support.vw_truss_system:
        return None
    candidates = []
    for construction in constructions:
        attached = attach_item(support, construction, plan_only=True,
                               method="missing_system_inclined_plan_geometry")
        if attached is None or attached.attachment.carrier_clearance_mm > config.ATTACHMENT_EXACT_DISTANCE_MM:
            continue
        carrier = next((item for item in construction.truss_segments
                        if item.id == attached.attachment.truss_id), None)
        if carrier and abs(carrier.end.z-carrier.start.z) >= carrier.geometric_length_mm*sin(radians(5.0)):
            candidates.append((construction, attached))
    if len(candidates) != 1:
        return None
    construction, attached = candidates[0]
    attached.attachment.confidence = "INFERRED"
    return construction, attached


def _dead_hang_top_attachment(support, target):
    """Resolve an explicit house rigging point to its nearest UUID port."""
    uuid = support.vw_truss_system_top
    hint = support.transfer_target_position
    candidates = []
    for truss in target.truss_segments:
        for port, value in truss.vw_connections.items():
            if value != uuid or port not in ("start", "end"):
                continue
            point = truss.start if port == "start" else truss.end
            distance = 0.0
            if hint is not None:
                distance = ((point.x - hint.x) ** 2 +
                            (point.y - hint.y) ** 2 +
                            (point.z - hint.z) ** 2) ** 0.5
            probe = replace(support, position=point)
            attached = attach_item(
                probe, target, plan_only=False,
                method="dead_hang_house_point_uuid")
            if attached:
                candidates.append((distance, truss.id, port, attached))
    if candidates:
        return min(candidates, key=lambda value: value[:3])[3]
    # Some carrier objects expose a UUID without a line endpoint. Only accept
    # the stored top hint when it independently satisfies the 3D tolerance.
    if hint is not None:
        return attach_item(
            replace(support, position=hint), target, plan_only=False,
            method="dead_hang_house_point_3d")
    return None


def _set_hoist_transfer_targets(document, constructions):
    for support in document.supports:
        target = _construction_for_uuid(
            support.vw_truss_system_top, constructions)
        if target is None:
            continue
        if support.support_kind == "dead_hang":
            target_attachment = _dead_hang_top_attachment(support, target)
        else:
            target_attachment = attach_item(
                support, target, plan_only=True,
                method="explicit_top_system_geometry")
        if target_attachment:
            support.transfer_target_construction_id = target.id
            support.transfer_target_station_mm = (
                target_attachment.attachment.global_station_mm)


def _attach_structural_links(document, constructions):
    for link in document.structural_links:
        supported = _construction_for_uuid(link.top_uuid, constructions)
        target = _construction_for_uuid(link.bottom_uuid, constructions)
        if supported is None or target is None or supported is target:
            continue
        virtual_support = Support(
            id=link.id, name=link.name or "Truss cross",
            position=link.position, is_structural_link=True,
            transfer_target_construction_id=target.id,
        )
        attached = attach_item(
            virtual_support, supported, plan_only=True,
            method="truss_cross_uuid_geometry")
        target_attachment = attach_item(
            virtual_support, target, plan_only=True,
            method="truss_cross_target_geometry")
        if attached and target_attachment:
            virtual_support.transfer_target_station_mm = (
                target_attachment.attachment.global_station_mm)
            attached.attachment.confidence = "EXACT"
            supported.supports.append(attached)


def _unassigned_support_diagnostic(support, constructions):
    """Return auditable evidence without converting proximity into attachment."""
    candidates = []
    for construction in constructions:
        for plan_only, label in ((False, "nearest_3d"), (True, "nearest_plan")):
            nearest = nearest_line_truss(
                support.position, construction.truss_segments, plan_only=plan_only)
            if nearest is None:
                continue
            clearance, axis_distance, truss_id, _, local_t, _, _, _ = nearest
            candidates.append((label, clearance, axis_distance, construction.id,
                               truss_id, local_t))
    result = {
        "missing_truss_system_identifier": not bool(support.vw_truss_system),
        "missing_top_truss_system_identifier": not bool(
            support.vw_truss_system_top),
    }
    for label in ("nearest_3d", "nearest_plan"):
        matches = [item for item in candidates if item[0] == label]
        if matches:
            _, clearance, axis_distance, construction_id, truss_id, local_t = min(
                matches, key=lambda item: item[1:])
            result[label] = {
                "construction_id": construction_id,
                "truss_id": truss_id,
                "carrier_clearance_mm": clearance,
                "axis_distance_mm": axis_distance,
                "local_fraction": local_t,
            }
    result["reason"] = (
        "missing_explicit_truss_system_identifier"
        if result["missing_truss_system_identifier"]
        else "no_safe_geometry_attachment")
    return result


def attach_document_objects(document, constructions):
    for attribute, objects in (
        ("supports", document.supports),
        ("point_loads", document.point_loads),
        ("distributed_loads", document.distributed_loads),
    ):
        for item in objects:
            if attribute == "supports":
                explicit = _explicit_support_attachment(item, constructions)
                if explicit is None:
                    explicit = _unresolved_explicit_inclined_attachment(
                        item, constructions)
                if explicit is None:
                    explicit = _missing_identifier_inclined_attachment(
                        item, constructions)
                if explicit:
                    construction, attached = explicit
                    construction.supports.append(attached)
                    continue
            candidates = []
            for construction in constructions:
                attached = attach_item(
                    item, construction, plan_only=False,
                    method=("geometry_3d_support" if attribute == "supports"
                            else "geometry_sphere"))
                if attached:
                    candidates.append((
                        attached.attachment.carrier_clearance_mm,
                        attached.attachment.distance_from_truss_axis_mm,
                        construction.id, construction, attached))
            if candidates:
                _, _, _, construction, attached = min(
                    candidates, key=lambda value: value[:3])
                if attribute == "distributed_loads" and item.end_position:
                    endpoint = attach_item(
                        replace(item, position=item.end_position), construction,
                        method="geometry_distributed_endpoint")
                    if endpoint:
                        attached.attachment.end_global_station_mm = (
                            endpoint.attachment.global_station_mm)
                getattr(construction, attribute).append(attached)
            else:
                unassigned_attribute = "unassigned_" + attribute
                getattr(document, unassigned_attribute).append(item)
                if attribute == "supports":
                    document.unassigned_support_diagnostics[item.id] = (
                        _unassigned_support_diagnostic(item, constructions))
    _set_hoist_transfer_targets(document, constructions)
    _attach_structural_links(document, constructions)
