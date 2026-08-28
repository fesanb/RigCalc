"""Compact, user-facing summary of one complete RigCalc run."""


def build_run_summary(document, constructions, primary, writeback,
                      cross_writeback, hoist_id_assignment=None,
                      notifications=None):
    notifications = notifications or []
    calculated = [item for item in primary["constructions"]
                  if item.get("status") == "preliminary"]
    uncalculated_ids = {
        item["construction_id"] for item in primary["constructions"]
        if item.get("status") != "preliminary"}
    failed_ids = {
        item["construction_id"] for item in primary["constructions"]
        if (item.get("status") == "preliminary" and
            not item.get("writeback_eligible", False))}
    writeback_failures = [
        item for result in (writeback, cross_writeback)
        for item in result.get("items", [])
        if item.get("status") != "written"]
    unassigned_hoists = [item for item in document.unassigned_supports
                         if item.support_kind == "hoist"]
    unassigned_dead_hangs = [item for item in document.unassigned_supports
                             if item.support_kind == "dead_hang"]
    unassigned = {
        "hoists": len(unassigned_hoists),
        "dead_hangs": len(unassigned_dead_hangs),
        "point_loads": len(document.unassigned_point_loads),
        "distributed_loads": len(document.unassigned_distributed_loads),
    }
    ignored = {}
    for record_name in document.ignored_record_types:
        if record_name == "Light Position Obj":
            # Hanging Positions are handled by the dedicated nested scanner.
            continue
        ignored[record_name] = ignored.get(record_name, 0)+1
    return {
        "hoist_ids": {
            "existing": (hoist_id_assignment or {}).get(
                "existing_count", 0),
            "assigned": (hoist_id_assignment or {}).get(
                "assigned_count", 0),
        },
        "found": {
            "constructions": len(constructions),
            "trusses": len(document.trusses),
            "motors": sum(item.support_kind == "hoist"
                          for item in document.supports),
            "dead_hangs": sum(item.support_kind == "dead_hang"
                              for item in document.supports),
            "point_loads": len(document.point_loads),
            "distributed_loads": len(document.distributed_loads),
            "truss_crosses": len(document.structural_links),
        },
        "calculated": {
            "constructions": len(calculated),
            "linear_primary": sum(
                item.get("primary_solver") == "linear" for item in calculated),
            "corotational_primary": sum(
                item.get("primary_solver") == "corotational"
                for item in calculated),
            "released_motor_supports": sum(
                item.get("released_support_count", 0) for item in calculated),
            "written_motors": sum(
                item.get("status") == "written"
                for item in writeback.get("items", [])),
            "written_truss_crosses": sum(
                item.get("status") == "written"
                for item in cross_writeback.get("items", [])),
        },
        "technical_errors": {
            "count": len(failed_ids)+len(writeback_failures),
            "construction_ids": sorted(failed_ids),
            "writeback_failure_count": len(writeback_failures),
        },
        "notifications": {
            "count": len(notifications),
            "load_errors": sum(
                item.get("class_name") == "RigCalc-Load" and
                item.get("severity") == "error"
                for item in notifications),
            "deflections": sum(
                item.get("class_name") == "RigCalc-Deflection"
                for item in notifications),
            "internal_errors": sum(
                item.get("class_name") == "RigCalc-Internal" and
                item.get("severity") == "error"
                for item in notifications),
        },
        "uncalculated_constructions": {
            "count": len(uncalculated_ids),
            "construction_ids": sorted(uncalculated_ids),
        },
        "unhandled_calculation_objects": {
            "count": sum(unassigned.values()),
            **unassigned,
        },
        "ignored_irrelevant_plugin_objects": {
            "count": sum(ignored.values()),
            "by_record": ignored,
        },
    }


def make_run_summary_text(summary):
    found = summary["found"]
    calculated = summary["calculated"]
    errors = summary["technical_errors"]
    uncalculated = summary.get("uncalculated_constructions", {})
    unhandled = summary["unhandled_calculation_objects"]
    ignored = summary["ignored_irrelevant_plugin_objects"]
    hoist_ids = summary.get("hoist_ids", {})
    notifications = summary.get("notifications", {})
    status = "REVIEW REQUIRED" if (
        errors["count"] or uncalculated.get("count", 0) or
        unhandled["count"] or notifications.get("load_errors", 0) or
        notifications.get("internal_errors", 0)) else "COMPLETE"
    return (
        "RIGCALC  /  RUN SUMMARY\n"
        "Status: {}\n\n"
        "--- MODEL --------------------------------\n"
        "Constructions: {}\n"
        "Truss objects: {}\n"
        "Hoists: {}\n"
        "New Hoist IDs: {}\n"
        "Dead hangs: {}\n"
        "Point loads: {}\n"
        "Distributed loads: {}\n"
        "Truss Cross objects: {}\n\n"
        "--- CALCULATION --------------------------\n"
        "Calculated constructions: {}/{}\n"
        "Linear primary results: {}\n"
        "Corotational primary results: {}\n"
        "Hoist results written: {}\n"
        "Truss Cross results written: {}\n"
        "Released hoist supports: {}\n\n"
        "--- REVIEW -------------------------------\n"
        "Load errors: {}\n"
        "Deflection markers: {}\n"
        "Internal-force errors: {}\n"
        "Technical errors: {}\n"
        "Uncalculated constructions: {}\n"
        "Unhandled calculation objects: {}\n"
        "  Hoists: {}\n"
        "  Dead hangs: {}\n"
        "  Point loads: {}\n"
        "  Distributed loads: {}\n"
        "Ignored irrelevant plug-in objects: {}"
    ).format(
        status, found["constructions"], found["trusses"], found["motors"],
        hoist_ids.get("assigned", 0),
        found["dead_hangs"],
        found["point_loads"], found["distributed_loads"],
        found["truss_crosses"], calculated["constructions"],
        found["constructions"], calculated["linear_primary"],
        calculated["corotational_primary"], calculated["written_motors"],
        calculated["written_truss_crosses"],
        calculated["released_motor_supports"],
        notifications.get("load_errors", 0),
        notifications.get("deflections", 0),
        notifications.get("internal_errors", 0), errors["count"],
        uncalculated.get("count", 0),
        unhandled["count"], unhandled["hoists"],
        unhandled["dead_hangs"],
        unhandled["point_loads"], unhandled["distributed_loads"],
        ignored["count"])
