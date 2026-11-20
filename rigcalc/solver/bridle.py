"""Leg forces of multi-leg bridles (GitHub issue #1).

A bridle carries the High Hook load of the hoist hanging from its apex plus
its own hardware weight.  Each leg runs from the apex to a house rigging
point.  Vectorworks stores leg lengths and trims but no explicit link to the
house point, so legs are matched jointly to the house points whose plan
position at the leg trim lies at the leg length from the apex (smallest
total error); the best assignment must be unambiguous.

Leg tensions T_i follow from equilibrium of the apex:
    sum(T_i * u_i) = (0, 0, W)
where u_i are unit vectors from the apex to the anchors.  Two and three legs
are solved (two legs by least squares, reporting any horizontal imbalance);
four legs are statically indeterminate and fail closed.

Results are calculation-basis values (with the run's safety factor).  The
unfactored values are reported next to the Vectorworks leg forces for
comparison.  Nothing is written to Vectorworks.
"""

from math import sqrt

GRAVITY_M_S2 = 9.80665
LENGTH_TOLERANCE_RATIO = 0.01
LENGTH_TOLERANCE_MM = 50.0
TRIM_TOLERANCE_MM = 100.0
IMBALANCE_RATIO = 0.01


def _distance(a, b):
    return sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2)


def _solve(matrix, vector):
    """Least-squares solution of a small dense system (normal equations)."""
    columns = len(matrix[0])
    normal = [[sum(matrix[r][i]*matrix[r][j] for r in range(len(matrix)))
               for j in range(columns)] for i in range(columns)]
    rhs = [sum(matrix[r][i]*vector[r] for r in range(len(matrix)))
           for i in range(columns)]
    size = columns
    augmented = [row[:]+[value] for row, value in zip(normal, rhs)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(augmented[r][column]))
        if abs(augmented[pivot][column]) <= 1.0e-12:
            raise ValueError("bridle_legs_parallel")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]/augmented[column][column]
            for k in range(column, size+1):
                augmented[row][k] -= factor*augmented[column][k]
    return [augmented[i][size]/augmented[i][i] for i in range(size)]


def _anchor(point, leg):
    """Leg attachment: house point in plan, at the leg's trim height.

    Vectorworks measures leg length to the trim, which sits slightly below
    the house point's geometric centre (25 mm in the test drawing).
    """
    return type(point.position)(point.position.x, point.position.y,
                                leg.trim_mm)


def _match_legs(bridle, points):
    """Assign legs to house points jointly (smallest total length error)."""
    from itertools import permutations

    candidates = [point for point in points if any(
        abs(point.position.z-leg.trim_mm) <= TRIM_TOLERANCE_MM
        for leg in bridle.legs)]
    best, second = None, None
    for chosen in permutations(candidates, len(bridle.legs)):
        errors = []
        for leg, point in zip(bridle.legs, chosen):
            error = abs(_distance(bridle.apex, _anchor(point, leg)) -
                        leg.length_mm)
            tolerance = max(LENGTH_TOLERANCE_MM,
                            LENGTH_TOLERANCE_RATIO*leg.length_mm)
            if (error > tolerance or
                    abs(point.position.z-leg.trim_mm) > TRIM_TOLERANCE_MM):
                break
            errors.append(error)
        else:
            total = sum(errors)
            if best is None or total < best[0]:
                best, second = (total, chosen), best
            elif second is None or total < second[0]:
                second = (total, chosen)
    if best is None:
        return None, ["bridle_leg_anchors_not_found"]
    if second is not None and second[0]-best[0] <= 1.0:
        return None, ["bridle_leg_anchors_ambiguous"]
    return list(best[1]), []


def calculate_bridles(document, hoist_outcomes, safety_factor=1.0):
    supports_by_uuid = {
        item.object_uuid.strip("{}").lower(): item
        for item in document.supports if item.object_uuid}
    outcomes = {item["support_id"]: item for item in hoist_outcomes}
    results = []
    for bridle in document.bridles:
        record = {
            "bridle_id": bridle.id, "index": bridle.index,
            "name": bridle.name, "bridle_type": bridle.bridle_type,
            "apex_mm": [bridle.apex.x, bridle.apex.y, bridle.apex.z],
            "weight_kg": bridle.weight_kg, "legs": [], "issues": [],
            "status": "not_calculated",
        }
        results.append(record)
        hoist = supports_by_uuid.get(
            bridle.connected_hoist_uuid.strip("{}").lower())
        if hoist is None:
            record["issues"].append("connected_hoist_not_found")
            continue
        record["hoist_id"] = hoist.hoist_id
        record["support_id"] = hoist.id
        outcome = outcomes.get(hoist.id, {})
        record["hoist_outcome"] = outcome.get("status")
        if outcome.get("status") not in ("calculated", "direct_geometry_load",
                                         "manual_direct_load"):
            record["issues"].append("connected_hoist_load_not_validated")
            continue
        high_hook_kg = outcome.get("high_hook_mass_kg") or 0.0
        apex_kg = high_hook_kg+bridle.weight_kg
        record["hoist_high_hook_kg"] = high_hook_kg
        record["apex_load_kg"] = apex_kg
        if len(bridle.legs) > 3:
            record["issues"].append("bridle_statically_indeterminate")
            continue
        anchors, issues = _match_legs(bridle, document.house_rigging_points)
        record["issues"].extend(issues)
        if issues:
            continue
        vectors = []
        for leg, anchor in zip(bridle.legs, anchors):
            point = _anchor(anchor, leg)
            length = _distance(bridle.apex, point)
            vectors.append(tuple((getattr(point, axis) -
                                  getattr(bridle.apex, axis))/length
                                 for axis in "xyz"))
        load_n = apex_kg*GRAVITY_M_S2
        matrix = [[vector[row] for vector in vectors] for row in range(3)]
        try:
            tensions = _solve(matrix, [0.0, 0.0, load_n])
        except ValueError as error:
            record["issues"].append(str(error))
            continue
        resultant = [sum(t*v[row] for t, v in zip(tensions, vectors))
                     for row in range(3)]
        imbalance = sqrt(resultant[0]**2+resultant[1]**2 +
                         (resultant[2]-load_n)**2)
        record["horizontal_imbalance_n"] = imbalance
        overloaded = False
        for leg, anchor, tension, vector in zip(bridle.legs, anchors,
                                                tensions, vectors):
            unfactored = tension/safety_factor if safety_factor else tension
            row = {
                "leg": leg.number, "house_rigging_point": anchor.id,
                "anchor_mm": [anchor.position.x, anchor.position.y,
                              anchor.position.z],
                "length_mm": leg.length_mm,
                "geometric_length_mm": _distance(bridle.apex,
                                                 _anchor(anchor, leg)),
                "force_n": tension, "force_unfactored_n": unfactored,
                "anchor_force_n": [-tension*value for value in vector],
                "vw_force_n": leg.vw_force_n,
                "max_force_n": leg.max_force_n,
            }
            if leg.max_force_n and tension > leg.max_force_n:
                row["overload"] = True
                overloaded = True
            record["legs"].append(row)
        if any(value < 0.0 for value in tensions):
            record["issues"].append("bridle_leg_in_compression")
        if imbalance > IMBALANCE_RATIO*load_n:
            record["issues"].append("bridle_apex_not_in_equilibrium")
        if overloaded:
            record["issues"].append("bridle_leg_overload")
        record["status"] = ("calculated" if not any(
            issue in ("bridle_leg_in_compression",
                      "bridle_apex_not_in_equilibrium")
            for issue in record["issues"]) else "diagnostic")
    return results


def make_bridle_text(results):
    lines = ["RIGCALC BRIDLES", "="*72, ""]
    if not results:
        lines.append("No multi-leg bridles found.")
    for item in results:
        lines.append("{} {} ({}) - {}".format(
            item["index"] or item["bridle_id"], item["bridle_type"],
            item.get("hoist_id", "-"), item["status"]))
        if "apex_load_kg" in item:
            lines.append("  Apex load {:.2f} kg = hoist High Hook {:.2f} kg"
                         " + bridle {:.2f} kg".format(
                             item["apex_load_kg"], item["hoist_high_hook_kg"],
                             item["weight_kg"]))
        for leg in item["legs"]:
            vw = leg.get("vw_force_n")
            lines.append(
                "  Leg {} -> {}: {:.1f} N (unfactored {:.1f} N; Vectorworks "
                "{}){}".format(
                    leg["leg"], leg["house_rigging_point"], leg["force_n"],
                    leg["force_unfactored_n"],
                    "{:.1f} N".format(vw) if vw is not None else "-",
                    " OVERLOAD" if leg.get("overload") else ""))
        for issue in item["issues"]:
            lines.append("  ISSUE: "+issue)
        lines.append("")
    return "\n".join(lines)
