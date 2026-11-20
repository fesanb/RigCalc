"""Writeback of calculated bridle leg and house rigging point forces.

RigCalc replaces the Braceworks/Production Assist bridle calculation, so a
validated result is written to the same fields Vectorworks displays:

* ``BridleObj``: ``ForceLeg1..n`` and ``ForceDownLeg`` (the hoist below the
  apex), all N;
* ``HouseRiggingPoint``: ``ForceX``, ``ForceY``, ``ForceZ`` (N, force on the
  point; Z negative = pulled down), summed over every leg anchored there.

Only bridles with status ``calculated`` are written.  A house rigging point
is written only when every bridle leg anchored to it comes from a calculated
bridle; otherwise it is left untouched and reported.  Every value is read
back and verified.
"""

from math import isfinite

from .records import get_parametric_info, safe_float

BRIDLE_RECORD = "BridleObj"
HOUSE_POINT_RECORD = "HouseRiggingPoint"
TOLERANCE_N = 0.01


def _format(value):
    return "{:.6f}".format(value)


def _write_and_verify(vs, handle, record, values):
    for field, value in values.items():
        vs.SetRField(handle, record, field, _format(value))
    vs.ResetObject(handle)
    _, readback = get_parametric_info(vs, handle)
    mismatches = {}
    for field, value in values.items():
        actual = safe_float(readback.get(field))
        if actual is None or abs(actual-value) > TOLERANCE_N:
            mismatches[field] = readback.get(field)
    return readback, mismatches


def write_bridle_forces(vs, document, bridle_results):
    bridles = {item.id: item for item in document.bridles}
    points = {item.id: item for item in document.house_rigging_points}
    results = []
    calculated = [item for item in bridle_results
                  if item.get("status") == "calculated"]
    blocked_points = set()
    for item in bridle_results:
        if item.get("status") != "calculated":
            results.append({"bridle_id": item["bridle_id"],
                            "status": "skipped_not_calculated",
                            "issues": item.get("issues", [])})
            # House points this bridle might load cannot be known reliably;
            # any point it is matched to is blocked below.
            for leg in item.get("legs", []):
                blocked_points.add(leg["house_rigging_point"])
    point_forces = {}
    for item in calculated:
        for leg in item["legs"]:
            force = point_forces.setdefault(leg["house_rigging_point"],
                                            [0.0, 0.0, 0.0])
            for axis in range(3):
                force[axis] += leg["anchor_force_n"][axis]
    if not calculated:
        return {"status": "nothing_to_write", "items": results}
    vs.NameUndoEvent("RigCalc bridle force writeback")
    for item in calculated:
        bridle = bridles.get(item["bridle_id"])
        values = {"ForceLeg{}".format(leg["leg"]): leg["force_n"]
                  for leg in item["legs"]}
        values["ForceDownLeg"] = item["down_leg_force_n"]
        if (bridle is None or bridle.source_ref is None or
                not all(isfinite(value) and value >= 0.0
                        for value in values.values())):
            results.append({"bridle_id": item["bridle_id"],
                            "status": "skipped_invalid"})
            continue
        record, old = get_parametric_info(vs, bridle.source_ref)
        if record != BRIDLE_RECORD:
            results.append({"bridle_id": item["bridle_id"],
                            "status": "skipped_not_bridle"})
            continue
        readback, mismatches = _write_and_verify(
            vs, bridle.source_ref, BRIDLE_RECORD, values)
        results.append({
            "bridle_id": item["bridle_id"], "index": item.get("index"),
            "status": "written" if not mismatches else "readback_mismatch",
            "values_n": values,
            "old": {field: old.get(field) for field in values},
            "new": {field: readback.get(field) for field in values},
            "mismatches": mismatches,
        })
    for point_id, force in sorted(point_forces.items()):
        point = points.get(point_id)
        if point_id in blocked_points:
            results.append({"house_rigging_point": point_id,
                            "status": "skipped_uncalculated_bridle_leg"})
            continue
        if point is None or point.source_ref is None:
            results.append({"house_rigging_point": point_id,
                            "status": "skipped_missing_object"})
            continue
        record, old = get_parametric_info(vs, point.source_ref)
        if record != HOUSE_POINT_RECORD:
            results.append({"house_rigging_point": point_id,
                            "status": "skipped_not_house_rigging_point"})
            continue
        values = dict(zip(("ForceX", "ForceY", "ForceZ"), force))
        readback, mismatches = _write_and_verify(
            vs, point.source_ref, HOUSE_POINT_RECORD, values)
        results.append({
            "house_rigging_point": point_id,
            "status": "written" if not mismatches else "readback_mismatch",
            "values_n": values,
            "old": {field: old.get(field) for field in values},
            "new": {field: readback.get(field) for field in values},
            "mismatches": mismatches,
        })
    status = ("written" if all(item["status"] == "written"
                               for item in results) else
              "completed_with_issues")
    return {"status": status, "items": results}
