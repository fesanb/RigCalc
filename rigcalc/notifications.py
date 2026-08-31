"""Pure calculation-result validation for user-facing notifications."""


LOAD_NOTIFICATION_CLASS = "RigCalc-Load"
DEFLECTION_NOTIFICATION_CLASS = "RigCalc-Deflection"
INTERNAL_NOTIFICATION_CLASS = "RigCalc-Internal"


def evaluate_hoist_overloads(calculation, tolerance_kg=0.1):
    """Return load errors for valid hoist reactions above rated capacity."""
    notifications = []
    for construction in calculation.get("constructions", []):
        if (construction.get("status") != "preliminary" or
                not construction.get("writeback_eligible", False)):
            continue
        for reaction in construction.get("reactions", []):
            if (reaction.get("is_structural_link") or
                    reaction.get("support_kind") != "hoist"):
                continue
            capacity = reaction.get("capacity_kg")
            load = reaction.get("reaction_mass_kg")
            if capacity is None or load is None or capacity <= 0:
                continue
            if load <= capacity + tolerance_kg:
                continue
            support_id = str(reaction.get("support_id", ""))
            hoist_id = str(reaction.get("support_hoist_id") or
                           reaction.get("support_name") or support_id)
            utilization = load / capacity
            notifications.append({
                "id": "hoist_overload:{}".format(support_id),
                "type": "hoist_overload",
                "severity": "error",
                "class_name": LOAD_NOTIFICATION_CLASS,
                "construction_id": construction.get("construction_id", ""),
                "support_id": support_id,
                "hoist_id": hoist_id,
                "actual_kg": load,
                "capacity_kg": capacity,
                "utilization": utilization,
                "message": "OVERLOAD\n{}\n{:.0f} / {:.0f} kg ({:.0f} %)".format(
                    hoist_id, load, capacity, utilization * 100.0),
            })
    return notifications


def evaluate_deflections(calculation):
    """Return informational deflection labels; no limit is assumed."""
    notifications = []
    for construction in calculation.get("constructions", []):
        if construction.get("status") != "preliminary":
            continue
        for index, span in enumerate(
                construction.get("deflection", {}).get("spans", []), 1):
            midspan = span.get("midspan")
            maximum = span.get("maximum")
            if not midspan or not maximum:
                continue
            ratio = span.get("midspan_deflection_ratio")
            ratio_text = "L/{:.0f}".format(ratio) if ratio else "L/-"
            construction_id = str(construction.get("construction_id", ""))
            notifications.append({
                "id": "deflection:{}:{}".format(construction_id, index),
                "type": "deflection",
                "severity": "info",
                "class_name": DEFLECTION_NOTIFICATION_CLASS,
                "construction_id": construction_id,
                "source_station_mm": maximum["station_mm"],
                "span_start_mm": span["span_start_mm"],
                "span_end_mm": span["span_end_mm"],
                "midspan_deflection_mm": midspan["deflection_mm"],
                "maximum_deflection_mm": maximum["deflection_mm"],
                "message": (
                    "DEFLECTION\n{}  {:.1f}-{:.1f} m\n"
                    "MID {:+.1f} mm ({}) | MAX {:+.1f} mm"
                ).format(
                    construction_id,
                    span["span_start_mm"] / 1000.0,
                    span["span_end_mm"] / 1000.0,
                    midspan["deflection_mm"], ratio_text,
                    maximum["deflection_mm"]),
            })
    return notifications


def _force_text(component, actual, capacity):
    if component.endswith("_nm"):
        unit, divisor = "kNm", 1000.0
    else:
        unit, divisor = "kN", 1000.0
    label = component.replace("_nm", "").replace("_n", "")
    return "{} {:.2f}/{:.2f} {} ({:.0f} %)".format(
        label, abs(actual)/divisor, capacity/divisor, unit,
        abs(actual)/capacity*100.0)


def evaluate_internal_forces(calculation, tolerance_ratio=1.0e-6):
    """Return component-wise cross-section capacity exceedances."""
    grouped = {}
    for construction in calculation.get("constructions", []):
        if (construction.get("status") != "preliminary" or
                not construction.get("writeback_eligible", False)):
            continue
        construction_id = str(construction.get("construction_id", ""))
        for element in construction.get("element_forces", []):
            section = element.get("cross_section", {})
            section_id = str(section.get("identifier", ""))
            capacities = section.get("capacities", {})
            for end_name, station_key in (("i", "start_station_mm"),
                                          ("j", "end_station_mm")):
                forces = element.get(end_name, {})
                station = element.get(station_key)
                if station is None:
                    continue
                key = (construction_id, round(station, 6), section_id)
                row = grouped.setdefault(key, {
                    "construction_id": construction_id,
                    "source_station_mm": station,
                    "cross_section_id": section_id,
                    "components": {},
                })
                for component, capacity in capacities.items():
                    actual = forces.get(component)
                    if capacity is None or actual is None:
                        continue
                    utilization = abs(actual) / capacity
                    if utilization <= 1.0 + tolerance_ratio:
                        continue
                    previous = row["components"].get(component)
                    if previous is None or utilization > previous["utilization"]:
                        row["components"][component] = {
                            "actual": actual, "capacity": capacity,
                            "utilization": utilization,
                        }
    notifications = []
    for row in grouped.values():
        if not row["components"]:
            continue
        components = sorted(
            row["components"].items(),
            key=lambda item: item[1]["utilization"], reverse=True)
        messages = [_force_text(name, value["actual"], value["capacity"])
                    for name, value in components]
        notifications.append({
            "id": "internal:{}:{:.3f}:{}".format(
                row["construction_id"], row["source_station_mm"],
                row["cross_section_id"]),
            "type": "internal_force_overload",
            "severity": "error",
            "class_name": INTERNAL_NOTIFICATION_CLASS,
            **row,
            "maximum_utilization": components[0][1]["utilization"],
            "message": "INTERNAL\n{}\n{}".format(
                row["cross_section_id"], "\n".join(messages)),
        })
    return notifications


def evaluate_support_model_failures(calculation):
    """Expose blocked tension-only support models at the affected hoist."""
    notifications = []
    for construction in calculation.get("constructions", []):
        if "tension_only_active_set_no_feasible_solution" not in construction.get("issues", []):
            continue
        negative = next((item for item in construction.get("reactions", [])
                         if item.get("reaction_mass_kg", 0.0) < -1.0e-6),
                        None)
        support_id = str((negative or {}).get("support_id", ""))
        hoist_id = str((negative or {}).get("support_hoist_id") or support_id)
        construction_id = str(construction.get("construction_id", ""))
        notifications.append({
            "id": "support_model:{}".format(construction_id),
            "type": "support_model_failure",
            "severity": "error",
            "class_name": LOAD_NOTIFICATION_CLASS,
            "construction_id": construction_id,
            "support_id": support_id,
            "message": "SUPPORT MODEL\n{}\n{}: cable slack / uplift\nNo feasible tension-only solution".format(
                construction_id, hoist_id or "support"),
        })
    return notifications


def evaluate_zero_hoist_outcomes(outcomes):
    """Mark hoists with no viable calculation without treating zero as load."""
    notifications = []
    for outcome in outcomes:
        if outcome.get("status") != "zero_not_calculated":
            continue
        hoist_id = str(outcome.get("hoist_id") or outcome["support_id"])
        notifications.append({
            "id": "hoist_zero_outcome:{}".format(outcome["support_id"]),
            "type": "hoist_zero_outcome",
            "severity": "error",
            "class_name": LOAD_NOTIFICATION_CLASS,
            "construction_id": "",
            "support_id": outcome["support_id"],
            "hoist_id": hoist_id,
            "message": "NO CALCULATION\n{}  0.00 kN\n{}".format(
                hoist_id, outcome.get("reason", "no_viable_carrier")),
        })
    return notifications


def evaluate_notifications(calculation):
    return (evaluate_hoist_overloads(calculation) +
            evaluate_deflections(calculation) +
            evaluate_internal_forces(calculation) +
            evaluate_support_model_failures(calculation))
