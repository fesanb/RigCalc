"""Auditable outcome for every discovered hoist.

An unavailable calculation is never represented by a silent omission.  Zero
outcomes are diagnostic only and deliberately never authorize writeback.
"""


def build_hoist_outcomes(document, calculation):
    """Return one explicit calculated or zero-force outcome per hoist."""
    reactions = {}
    constructions = {}
    for construction in calculation.get("constructions", []):
        construction_id = construction.get("construction_id", "")
        for reaction in construction.get("reactions", []):
            if (reaction.get("support_kind") == "hoist" and
                    not reaction.get("is_structural_link")):
                reactions[reaction.get("support_id")] = reaction
                constructions[reaction.get("support_id")] = construction

    outcomes = []
    for support in document.supports:
        if support.support_kind != "hoist":
            continue
        reaction = reactions.get(support.id)
        construction = constructions.get(support.id)
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
            outcome = {
                "support_id": support.id,
                "hoist_id": support.hoist_id,
                "status": "zero_not_calculated",
                "construction_id": "",
                "reaction_mass_kg": 0.0,
                "high_hook_mass_kg": 0.0,
                "writeback_eligible": False,
                "reason": diagnostic.get("reason", "no_viable_carrier"),
                "association_diagnostic": diagnostic,
            }
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
