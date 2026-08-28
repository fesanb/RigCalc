"""Assign stable human-readable IDs to Vectorworks hoists with blank IDs."""

from .records import get_parametric_info, safe_float


def populate_missing_hoist_ids(vs):
    handles = []
    vs.ForEachObject(handles.append, "((T=86))")
    hoists = []
    used = set()
    for handle in handles:
        record_name, fields = get_parametric_info(vs, handle)
        if record_name != "BrxHoist":
            continue
        identifier = str(fields.get("HoistID", "")).strip()
        if identifier:
            used.add(identifier.casefold())
        hoists.append((
            handle, fields, identifier,
            safe_float(fields.get("OriginY"), 0.0),
            safe_float(fields.get("OriginX"), 0.0),
        ))

    # Existing M numbers are never changed or reused.
    next_number = 1

    def next_identifier():
        nonlocal next_number
        while "m{}".format(next_number) in used:
            next_number += 1
        value = "M{}".format(next_number)
        used.add(value.casefold())
        next_number += 1
        return value

    results = []
    blanks = [item for item in hoists if not item[2]]
    # Stable initial ordering: drawing rows from top to bottom, then left to
    # right. Once written, later runs preserve the assigned IDs.
    blanks.sort(key=lambda item: (-item[3], item[4], repr(item[0])))
    if blanks:
        try:
            vs.NameUndoEvent("RigCalc Hoist ID assignment")
        except Exception:
            pass
    for handle, _, _, _, _ in blanks:
        identifier = next_identifier()
        vs.SetRField(handle, "BrxHoist", "HoistID", identifier)
        vs.ResetObject(handle)
        _, readback = get_parametric_info(vs, handle)
        actual = str(readback.get("HoistID", "")).strip()
        results.append({
            "hoist_id": identifier,
            "status": "written" if actual == identifier else "readback_mismatch",
            "readback": actual,
        })
    return {
        "status": ("written" if results and all(
            item["status"] == "written" for item in results)
                   else "nothing_to_write" if not results
                   else "completed_with_issues"),
        "existing_count": len(hoists) - len(blanks),
        "assigned_count": len(results),
        "items": results,
    }
