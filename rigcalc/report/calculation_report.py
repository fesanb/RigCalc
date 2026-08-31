"""Text rendering for solver results; mechanics live in rigcalc.solver."""


def _force_row(end, forces):
    return (
        "    {:>1}  N {:+12.3f} N  Vy {:+12.3f} N  Vz {:+12.3f} N  "
        "T {:+12.3f} Nm  My {:+12.3f} Nm  Mz {:+12.3f} Nm"
    ).format(end, forces["N_n"], forces["Vy_n"], forces["Vz_n"],
             forces["T_nm"], forces["My_nm"], forces["Mz_nm"])


def make_calculation_text(data):
    lines = [
        "RIGCALC PRELIMINARY CALCULATION",
        "=" * 72,
        "DO NOT WRITE THESE VALUES TO VECTORWORKS YET",
        "",
    ]
    for item in data["constructions"]:
        lines.extend([
            ("{} ({})".format(item.get("construction_name"),
                              item["construction_id"])
             if item.get("construction_name") and
             item.get("construction_name") != item["construction_id"]
             else item["construction_id"]),
            "-" * 72,
            "Status: {}".format(item["status"]),
            "Method: {}".format(item.get("method") or "-"),
            "Primary solver: {}".format(item.get("primary_solver") or "-"),
            "Applied mass: {:.2f} kg".format(item["total_applied_mass_kg"]),
        ])
        validation = item.get("validation", {})
        if validation:
            lines.append(
                "Validation: equilibrium={} support model={} numerical={} "
                "load model={}".format(
                    "yes" if validation.get("equilibrium_valid") else "no",
                    "yes" if validation.get("support_model_valid") else "no",
                    "yes" if validation.get("numerically_valid") else "no",
                    "yes" if validation.get("load_model_valid") else "no"))
        numerical = item.get("numerical_diagnostics", {})
        if numerical:
            lines.append(
                "Numerical diagnostics: method={} min scaled pivot={:.3e} "
                "relative residual={:.3e} refinements={}".format(
                    numerical.get("method", "-"),
                    numerical.get("minimum_scaled_pivot", 0.0),
                    numerical.get("relative_reduced_residual", 0.0),
                    numerical.get("iterative_refinement_steps", 0)))
        for reaction in item["reactions"]:
            support_state = (
                " [released tension-only support]"
                if reaction.get("support_active") is False else "")
            support_label = reaction.get("support_hoist_id") or reaction["support_id"]
            if support_label != reaction["support_id"]:
                support_label += " [{}]".format(reaction["support_id"])
            reaction_line = (
                "  {} at {:.3f} m: reaction {:.2f} kg + hoist/chain {:.2f} kg "
                "= preliminary high hook {:.2f} kg (capacity {:.2f} kg){}".format(
                    support_label, reaction["station_mm"] / 1000.0,
                    reaction["reaction_mass_kg"],
                    reaction["hoist_and_chain_mass_kg"],
                    reaction["preliminary_high_hook_mass_kg"],
                    reaction["capacity_kg"],
                    support_state,
                ))
            unconstrained = reaction.get("unconstrained_reaction_mass_kg")
            if (unconstrained is not None and
                    abs(unconstrained-reaction["reaction_mass_kg"]) > 1.0e-6):
                reaction_line += (
                    " [unconstrained signed reaction: {:+.2f} kg]".format(
                        unconstrained))
            lines.append(reaction_line)
        stations = item.get("stations", [])
        deflection = item.get("deflection", {})
        elements = item.get("element_forces", [])
        if deflection.get("maximum"):
            maximum = deflection["maximum"]
            lines.extend([
                "", "  VERTICAL DEFLECTION",
                "    Maximum: {:+.2f} mm at {:.3f} m".format(
                    maximum["deflection_mm"],
                    maximum["station_mm"] / 1000.0),
            ])
            for span in deflection.get("spans", []):
                midspan = span["midspan"]
                ratio = span["midspan_deflection_ratio"]
                ratio_text = ("L/{:.0f}".format(ratio)
                              if ratio is not None else "no deflection")
                lines.append(
                    "    Span {:.3f}-{:.3f} m: midspan {:+.2f} mm at "
                    "{:.3f} m ({}) | maximum {:+.2f} mm at {:.3f} m".format(
                        span["span_start_mm"] / 1000.0,
                        span["span_end_mm"] / 1000.0,
                        midspan["deflection_mm"],
                        midspan["station_mm"] / 1000.0,
                        ratio_text,
                        span["maximum"]["deflection_mm"],
                        span["maximum"]["station_mm"] / 1000.0))
        if stations:
            lines.extend(["", "  STATION DEFORMATIONS (global axes)"])
            for station in stations:
                value = station["displacements"]
                lines.append(
                    "    {:10.3f} m  u=({:+.6e}, {:+.6e}, {:+.6e}) m  "
                    "r=({:+.6e}, {:+.6e}, {:+.6e}) rad".format(
                        station["station_mm"] / 1000.0,
                        value["ux_m"], value["uy_m"], value["uz_m"],
                        value["rx_rad"], value["ry_rad"], value["rz_rad"]))
        if elements:
            lines.extend(["", "  ELEMENT END FORCES (local axes)"])
            for element in elements:
                lines.append("    {}  {:.3f} -> {:.3f} m".format(
                    element["element_id"],
                    element["start_station_mm"] / 1000.0,
                    element["end_station_mm"] / 1000.0))
                lines.append(_force_row("i", element["i"]))
                lines.append(_force_row("j", element["j"]))
        elif item.get("status") == "preliminary":
            lines.extend([
                "", "  SECTION RESULTS",
                "    unavailable: this result has no reported element section forces",
            ])
        for issue in item["issues"]:
            lines.append("  ISSUE: " + issue)
        lines.append("")
    return "\n".join(lines)
