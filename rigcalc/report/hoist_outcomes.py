"""Auditable outcome for every discovered hoist.

An unavailable calculation is never represented by a silent omission.  Zero
outcomes are diagnostic only and deliberately never authorize writeback.
"""

from math import sqrt

from rigcalc import config


def _attachment_evidence(attached):
    attachment = attached.attachment
    return {
        "truss_id": attachment.truss_id,
        "method": attachment.method,
        "confidence": attachment.confidence,
        "distance_from_truss_axis_mm": attachment.distance_from_truss_axis_mm,
        "carrier_clearance_mm": attachment.carrier_clearance_mm,
        "global_station_mm": attachment.global_station_mm,
    }


def _direct_loads_for_free_hoist(support, document):
    """Return unique point loads directly under an otherwise free hoist.

    This does not infer a truss relationship.  It is intentionally limited to
    unassigned point loads at the lower hook and refuses a load shared by
    multiple free hoists.
    """
    candidates = []
    for load in document.unassigned_point_loads:
        if load.weight_kg is None:
            continue
        distance = sqrt(
            (load.position.x-support.position.x) ** 2 +
            (load.position.y-support.position.y) ** 2 +
            (load.position.z-support.position.z) ** 2)
        if distance <= config.DIRECT_HOIST_LOAD_DISTANCE_MM:
            candidates.append((distance, load))
    if not candidates:
        return []
    nearest_distance = min(item[0] for item in candidates)
    nearest = [item for item in candidates
               if abs(item[0]-nearest_distance) <= 1.0e-6]
    if len(nearest) != 1:
        return []
    return nearest


def build_hoist_outcomes(document, calculation, topology_constructions=None):
    """Return one explicit calculated or zero-force outcome per hoist."""
    reactions = {}
    result_by_support = {}
    for construction in calculation.get("constructions", []):
        construction_id = construction.get("construction_id", "")
        for reaction in construction.get("reactions", []):
            if (reaction.get("support_kind") == "hoist" and
                    not reaction.get("is_structural_link")):
                reactions[reaction.get("support_id")] = reaction
                result_by_support[reaction.get("support_id")] = construction

    associated = {}
    for construction in topology_constructions or []:
        for attached in construction.supports:
            if attached.item.support_kind == "hoist":
                associated[attached.item.id] = (construction, attached)

    outcomes = []
    for support in document.supports:
        if support.support_kind != "hoist":
            continue
        reaction = reactions.get(support.id)
        construction = result_by_support.get(support.id)
        if reaction is not None and construction is not None:
            eligible = bool(construction.get("writeback_eligible", False))
            status = "calculated" if eligible else "diagnostic_only"
            outcome = {
                "support_id": support.id,
                "hoist_id": support.hoist_id,
                "status": status,
                "construction_id": construction.get("construction_id", ""),
                "reaction_mass_kg": reaction.get("reaction_mass_kg", 0.0),
                "high_hook_mass_kg": reaction.get(
                    "preliminary_high_hook_mass_kg", 0.0),
                "writeback_eligible": eligible,
                "reason": ("validated_physical_model" if eligible else
                           "; ".join(construction.get("issues", [])) or
                           "calculation_not_writeback_eligible"),
            }
        else:
            diagnostic = document.unassigned_support_diagnostics.get(
                support.id, {})
            attached_construction, attached = associated.get(
                support.id, (None, None))
            associated_result = next((item for item in calculation.get(
                "constructions", []) if attached_construction is not None and
                item.get("construction_id") == attached_construction.id), None)
            direct_loads = _direct_loads_for_free_hoist(support, document)
            if direct_loads:
                # A free hoist is not a solved construction. Its palette and
                # report outcome must show the user-maintained Vectorworks
                # mass, not an analysis-only safety-factor variant.
                direct_mass = sum(
                    item.unfactored_weight_kg
                    if item.unfactored_weight_kg is not None else item.weight_kg
                    for _, item in direct_loads)
                outcome = {
                    "support_id": support.id,
                    "hoist_id": support.hoist_id,
                    "status": "direct_geometry_load",
                    "construction_id": "",
                    "reaction_mass_kg": direct_mass,
                    "high_hook_mass_kg": (
                        direct_mass + (support.weight_with_chain_raw_kg or
                                       support.weight_with_chain_kg)),
                    "writeback_eligible": False,
                    "reason": "direct_free_hoist_load_geometry",
                    "direct_load_evidence": [{
                        "load_id": item.id, "record_type": item.record_type,
                        "mass_kg": item.weight_kg,
                        "distance_mm": distance,
                    } for distance, item in direct_loads],
                }
                outcomes.append(outcome)
                continue
            if support.manual_load_raw_kg > 0.0 or support.manual_load_kg > 0.0:
                manual_mass = (support.manual_load_raw_kg or
                               support.manual_load_kg)
                outcome = {
                    "support_id": support.id,
                    "hoist_id": support.hoist_id,
                    "status": "manual_direct_load",
                    "construction_id": "",
                    "reaction_mass_kg": manual_mass,
                    "high_hook_mass_kg": (
                        manual_mass + (support.weight_with_chain_raw_kg or
                                       support.weight_with_chain_kg)),
                    "writeback_eligible": False,
                    "reason": "manual_roof_force_no_deadload_weight",
                    "manual_input_field": "RoofForceNoDeadloadWeight",
                }
                outcomes.append(outcome)
                continue
            reason = diagnostic.get("reason")
            if reason is None and associated_result is not None:
                reason = ("; ".join(associated_result.get("issues", [])) or
                          "construction_not_calculated")
            if reason is None:
                reason = "no_viable_carrier"
            # A hoist with no carrier, nearby load, or manual load is not an
            # error. Leave its user-managed Vectorworks values untouched.
            has_no_nearby_carrier = (
                attached is None and
                (not diagnostic.get("nearest_3d") or
                 diagnostic["nearest_3d"].get(
                     "carrier_clearance_mm", 0.0) >
                 config.ATTACHMENT_SEARCH_RADIUS_MM))
            status = ("exempt_not_connected" if has_no_nearby_carrier else
                      "zero_not_calculated")
            outcome = {
                "support_id": support.id,
                "hoist_id": support.hoist_id,
                "status": status,
                "construction_id": "",
                "reaction_mass_kg": 0.0,
                "high_hook_mass_kg": 0.0,
                "writeback_eligible": False,
                "reason": ("exempt_not_connected" if
                           status == "exempt_not_connected" else reason),
                "association_diagnostic": diagnostic,
            }
            if attached is not None:
                outcome["association_evidence"] = _attachment_evidence(
                    attached)
        outcomes.append(outcome)
    return outcomes


def make_hoist_outcomes_text(outcomes):
    lines = ["RIGCALC HOIST OUTCOMES", "=" * 72, ""]
    for outcome in outcomes:
        label = outcome["hoist_id"] or outcome["support_id"]
        if outcome["status"] == "zero_not_calculated":
            value = "0.00 kN"
        else:
            value = "{:.2f} kg ({:.2f} kN)".format(
                outcome["reaction_mass_kg"],
                outcome["reaction_mass_kg"] * 9.80665 / 1000.0)
        lines.append("{}: {} [{}]".format(label, value, outcome["status"]))
        lines.append("  reason: {}".format(outcome["reason"]))
    return "\n".join(lines) + "\n"
