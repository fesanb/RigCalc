"""Auditable outcome for every discovered hoist.

An unavailable calculation is never represented by a silent omission.  Zero
outcomes are diagnostic only and deliberately never authorize writeback.
"""


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
            reason = diagnostic.get("reason")
            if reason is None and associated_result is not None:
                reason = ("; ".join(associated_result.get("issues", [])) or
                          "construction_not_calculated")
            if reason is None:
                reason = "no_viable_carrier"
            outcome = {
                "support_id": support.id,
                "hoist_id": support.hoist_id,
                "status": "zero_not_calculated",
                "construction_id": "",
                "reaction_mass_kg": 0.0,
                "high_hook_mass_kg": 0.0,
                "writeback_eligible": False,
                "reason": reason,
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
