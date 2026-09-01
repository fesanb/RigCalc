"""Confirmed writeback of calculated High Hook values to BrxHoist objects."""

from math import isfinite

from .hoist_fields import (HIGH_HOOK_FORCE_FIELD, HIGH_HOOK_WEIGHT_FIELD,
                           high_hook_field_values)
from .records import get_parametric_info, safe_float


def _write_candidates(document, calculation):
    supports = {item.id: item for item in document.supports}
    candidates, skipped = [], []
    for construction in calculation["constructions"]:
        if (construction["status"] != "preliminary" or
                not construction.get("writeback_eligible", False)):
            continue
        for reaction in construction["reactions"]:
            if reaction.get("is_structural_link"):
                continue
            support = supports.get(reaction["support_id"])
            if support is None or support.source_ref is None:
                continue
            if reaction.get("support_active") is False:
                skipped.append({
                    "support_id": support.id, "hoist_id": support.hoist_id,
                    "construction_id": construction["construction_id"],
                    "status": "skipped_slack_or_released_support",
                })
                continue
            mass_kg = reaction.get("preliminary_high_hook_mass_kg")
            if (not isinstance(mass_kg, (int, float)) or
                    not isfinite(mass_kg) or mass_kg < 0.0):
                skipped.append({
                    "support_id": support.id, "hoist_id": support.hoist_id,
                    "construction_id": construction["construction_id"],
                    "status": "skipped_invalid_high_hook_mass",
                })
                continue
            candidates.append({
                "construction_id": construction["construction_id"],
                "support": support,
                "mass_kg": mass_kg,
            })
    return candidates, skipped


def write_high_hook_values(vs, document, calculation, confirm=True):
    candidates, skipped = _write_candidates(document, calculation)
    if not candidates:
        return {"status": "nothing_to_write", "items": skipped}

    preview = []
    for item in candidates:
        support = item["support"]
        label = support.hoist_id or support.name or support.id
        preview.append("{}: {:.2f} kg".format(label, item["mass_kg"]))
    message = (
        "RigCalc High Hook writeback\n\n"
        "The following calculated values will be written to Vectorworks:\n\n"
        "{}\n\nContinue?".format("\n".join(preview)))
    if confirm and not vs.YNDialog(message):
        return {"status": "cancelled", "items": []}

    vs.NameUndoEvent("RigCalc High Hook writeback")
    results = list(skipped)
    for candidate in candidates:
        support = candidate["support"]
        handle = support.source_ref
        record_name, old_fields = get_parametric_info(vs, handle)
        if record_name != "BrxHoist":
            results.append({
                "support_id": support.id, "hoist_id": support.hoist_id,
                "status": "skipped_not_brhoist"})
            continue
        values = high_hook_field_values(candidate["mass_kg"])
        for field, value in values.items():
            vs.SetRField(handle, "BrxHoist", field, value)
        vs.ResetObject(handle)
        _, readback = get_parametric_info(vs, handle)
        expected_mass_g = candidate["mass_kg"] * 1000.0
        actual_mass_g = safe_float(readback.get(HIGH_HOOK_WEIGHT_FIELD))
        verified = (actual_mass_g is not None and
                    abs(actual_mass_g - expected_mass_g) <= 0.01)
        results.append({
            "support_id": support.id,
            "hoist_id": support.hoist_id,
            "construction_id": candidate["construction_id"],
            "status": "written" if verified else "readback_mismatch",
            "mass_kg": candidate["mass_kg"],
            "old_high_hook_weight_raw": old_fields.get(HIGH_HOOK_WEIGHT_FIELD),
            "new_high_hook_weight_raw": readback.get(HIGH_HOOK_WEIGHT_FIELD),
            "new_high_hook_force_raw": readback.get(HIGH_HOOK_FORCE_FIELD),
        })
    status = ("written" if results and
              all(item["status"] == "written" for item in results)
              else "completed_with_issues")
    return {"status": status, "items": results}
