"""Verified force writeback for BrxCustomTrussCross structural links."""

from .hoist_fields import STANDARD_GRAVITY_M_S2
from .records import get_parametric_info, safe_float


RECORD_NAME = "BrxCustomTrussCross"
FORCE_FIELD = "Force"


def _write_candidates(document, calculation):
    links = {item.id: item for item in document.structural_links}
    result = []
    for construction in calculation["constructions"]:
        if (construction["status"] != "preliminary" or
                not construction.get("writeback_eligible", False)):
            continue
        for reaction in construction["reactions"]:
            if not reaction.get("is_structural_link"):
                continue
            link = links.get(reaction["support_id"])
            if link is None or link.source_ref is None:
                continue
            result.append({
                "construction_id": construction["construction_id"],
                "link": link,
                "force_n": (reaction["reaction_mass_kg"] *
                            STANDARD_GRAVITY_M_S2),
            })
    return result


def write_truss_cross_forces(vs, document, calculation, confirm=True):
    candidates = _write_candidates(document, calculation)
    if not candidates:
        return {"status": "nothing_to_write", "items": []}
    preview = ["{}: {:+.2f} N".format(
        item["link"].name or item["link"].id, item["force_n"])
        for item in candidates]
    if confirm and not vs.YNDialog(
            "RigCalc truss-cross writeback\n\n"
            "The following calculated forces will be written to Force:\n\n"
            "{}\n\nContinue?".format("\n".join(preview))):
        return {"status": "cancelled", "items": []}
    vs.NameUndoEvent("RigCalc truss-cross force writeback")
    results = []
    for candidate in candidates:
        link, force_n = candidate["link"], candidate["force_n"]
        record_name, old_fields = get_parametric_info(vs, link.source_ref)
        if record_name != RECORD_NAME:
            results.append({"link_id": link.id,
                            "status": "skipped_not_truss_cross"})
            continue
        raw_value = "{:.6f}".format(force_n)
        vs.SetRField(link.source_ref, RECORD_NAME, FORCE_FIELD, raw_value)
        vs.ResetObject(link.source_ref)
        _, readback = get_parametric_info(vs, link.source_ref)
        actual = safe_float(readback.get(FORCE_FIELD))
        verified = actual is not None and abs(actual-force_n) <= 0.01
        results.append({
            "link_id": link.id,
            "construction_id": candidate["construction_id"],
            "status": "written" if verified else "readback_mismatch",
            "force_n": force_n,
            "old_force_raw": old_fields.get(FORCE_FIELD),
            "new_force_raw": readback.get(FORCE_FIELD),
        })
    status = ("written" if results and
              all(item["status"] == "written" for item in results)
              else "completed_with_issues")
    return {"status": status, "items": results}
