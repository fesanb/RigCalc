"""Compare solver branches and select a validated primary result."""

from copy import deepcopy


def compare_calculations(linear, nonlinear):
    nonlinear_by_id = {
        item["construction_id"]: item
        for item in nonlinear["constructions"]}
    rows = []
    for linear_item in linear["constructions"]:
        nonlinear_item = nonlinear_by_id.get(linear_item["construction_id"])
        if nonlinear_item is None:
            continue
        nonlinear_reactions = {
            item["support_id"]: item for item in nonlinear_item["reactions"]}
        reaction_rows = []
        for reaction in linear_item["reactions"]:
            other = nonlinear_reactions.get(reaction["support_id"])
            if other is None:
                continue
            linear_mass = reaction["reaction_mass_kg"]
            nonlinear_mass = other["reaction_mass_kg"]
            reaction_rows.append({
                "support_id": reaction["support_id"],
                "linear_mass_kg": linear_mass,
                "nonlinear_mass_kg": nonlinear_mass,
                "difference_kg": nonlinear_mass-linear_mass,
            })

        def maximum(stations, field):
            return max([abs(item["displacements"][field])
                        for item in stations] + [0.0])

        rows.append({
            "construction_id": linear_item["construction_id"],
            "construction_name": linear_item.get(
                "construction_name", linear_item["construction_id"]),
            "nonlinear_converged": nonlinear_item.get("converged", False),
            "linear_max_abs_uz_m": maximum(
                linear_item.get("stations", []), "uz_m"),
            "nonlinear_max_abs_uz_m": maximum(
                nonlinear_item.get("stations", []), "uz_m"),
            "nonlinear_max_abs_ux_m": maximum(
                nonlinear_item.get("stations", []), "ux_m"),
            "reactions": reaction_rows,
        })
    return {"constructions": rows}


def select_primary_calculation(linear, nonlinear):
    nonlinear_by_id = {
        item["construction_id"]: item
        for item in nonlinear["constructions"]}
    selected = []
    for linear_item in linear["constructions"]:
        nonlinear_item = nonlinear_by_id.get(linear_item["construction_id"])
        use_nonlinear = bool(
            nonlinear_item and len(nonlinear_item.get("reactions", [])) >= 3 and
            nonlinear_item.get("converged") and
            nonlinear_item.get("validation", {}).get(
                "vertical_equilibrium_ok") and
            nonlinear_item.get("validation", {}).get(
                "moment_equilibrium_ok", False) and
            nonlinear_item.get("validation", {}).get(
                "support_model_valid", False) and
            nonlinear_item.get("validation", {}).get(
                "numerically_valid", False) and
            nonlinear_item.get("validation", {}).get(
                "load_model_valid", False) and
            nonlinear_item.get("writeback_eligible", False) and
            not any(issue.startswith("upstream_nonlinear_")
                    for issue in nonlinear_item.get("issues", [])))
        item = deepcopy(nonlinear_item if use_nonlinear else linear_item)
        item["primary_solver"] = (
            "corotational" if use_nonlinear else "linear")
        if use_nonlinear:
            item["status"] = "preliminary"
            item["writeback_eligible"] = True
        selected.append(item)
    return {
        "status": "PRELIMINARY_PRIMARY_CALCULATION",
        "limitations": list(linear.get("limitations", [])),
        "unassigned": deepcopy(linear.get("unassigned", {})),
        "constructions": selected,
    }


def make_comparison_text(comparison):
    lines = ["RIGCALC SOLVER COMPARISON", "="*72, ""]
    for item in comparison["constructions"]:
        lines.extend([
            ("{} ({})".format(item.get("construction_name"),
                              item["construction_id"])
             if item.get("construction_name") and
             item.get("construction_name") != item["construction_id"]
             else item["construction_id"]), "-"*72,
            "Nonlinear converged: {}".format(item["nonlinear_converged"]),
            "Max |uz| linear/nonlinear: {:.6f} / {:.6f} m".format(
                item["linear_max_abs_uz_m"],
                item["nonlinear_max_abs_uz_m"]),
            "Max |ux| nonlinear: {:.6f} m".format(
                item["nonlinear_max_abs_ux_m"]),
            "  REACTIONS",
        ])
        for reaction in item["reactions"]:
            lines.append(
                "    {}: linear {:+.3f} kg, nonlinear {:+.3f} kg, "
                "difference {:+.3f} kg".format(
                    reaction["support_id"], reaction["linear_mass_kg"],
                    reaction["nonlinear_mass_kg"], reaction["difference_kg"]))
        lines.append("")
    return "\n".join(lines)
