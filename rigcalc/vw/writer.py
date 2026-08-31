import json
import os

from rigcalc import config
from rigcalc.normalization import normalize_inventory
from rigcalc.notifications import (evaluate_notifications,
                                   evaluate_zero_hoist_outcomes)
from rigcalc.report import (build_run_summary, make_calculation_text,
                            make_hoist_outcomes_text, make_text_report,
                            build_hoist_outcomes,
                            write_json_report)
from rigcalc.solver import (calculate_corotational_reactions,
                            calculate_reactions, compare_calculations,
                            make_comparison_text, select_primary_calculation)
from .hoist_writeback import write_high_hook_values
from .notifications import write_notification_markers
from .truss_cross_writeback import write_truss_cross_forces
from .summary_dialog import show_run_summary_dialog


def report_output_directory():
    rigcalc_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(rigcalc_root, config.OUTPUT_DIRECTORY_NAME)


def write_reports(vs, document, constructions, inventory=None,
                  included_layers=None, progress=None,
                  cable_load_kg_m=0.0,
                  safety_factor=1.0,
                  hoist_id_assignment=None):
    output_dir = report_output_directory()
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "rigcalc_hoist_ids.json"),
              "w", encoding="utf-8") as stream:
        json.dump(hoist_id_assignment or {
            "status": "not_run", "items": []}, stream,
            ensure_ascii=False, indent=2)
    if progress:
        progress("start", 4, "Writing model reports 0/4")
    text_path = os.path.join(output_dir, config.REPORT_BASENAME + ".txt")
    json_path = os.path.join(output_dir, config.REPORT_BASENAME + ".json")
    with open(text_path, "w", encoding="utf-8") as stream:
        stream.write(make_text_report(document, constructions))
    settings = {
        "endpoint_tolerance_mm": config.ENDPOINT_TOLERANCE_MM,
        "collinear_longitudinal_tolerance_mm": config.COLLINEAR_LONGITUDINAL_TOLERANCE_MM,
        "collinear_lateral_tolerance_mm": config.COLLINEAR_LATERAL_TOLERANCE_MM,
        "collinear_angle_tolerance_deg": config.COLLINEAR_ANGLE_TOLERANCE_DEG,
        "corner_tolerance_mm": config.CORNER_TOLERANCE_MM,
        "attachment_warning_distance_mm": config.ATTACHMENT_WARNING_DISTANCE_MM,
        "attachment_search_radius_mm": config.ATTACHMENT_SEARCH_RADIUS_MM,
        "included_layers": included_layers or [],
        "cable_load_kg_m": cable_load_kg_m,
        "safety_factor": safety_factor,
    }
    write_json_report(json_path, document, constructions, settings)
    if progress:
        progress("update", 1, "Writing model reports 1/4")
    normalized = {"summary": {
        "load_component_count": 0, "explicit_connection_count": 0}}
    if config.WRITE_DEVELOPMENT_INVENTORY:
        inventory_path = os.path.join(output_dir, "rigcalc_inventory.json")
        with open(inventory_path, "w", encoding="utf-8") as stream:
            json.dump({"plugin_objects": inventory or []}, stream,
                      ensure_ascii=False, indent=2)
        normalized_path = os.path.join(output_dir, "rigcalc_normalized.json")
        normalized = normalize_inventory(
            inventory or [], included_layers=included_layers)
        with open(normalized_path, "w", encoding="utf-8") as stream:
            json.dump(normalized, stream, ensure_ascii=False, indent=2)
    section_path = os.path.join(output_dir, "rigcalc_cross_sections.json")
    section_rows = {}
    for truss in document.trusses:
        section = truss.mechanical_section
        key = truss.cross_section_id or "<missing>"
        row = section_rows.setdefault(key, {
            "cross_section_id": key, "truss_ids": [],
            "properties": None, "issues": [],
        })
        row["truss_ids"].append(truss.id)
        if section:
            row["properties"] = {
                "identifier": section.identifier, "name": section.name,
                "manufacturer": section.manufacturer,
                "material_name": section.material_name,
                "area_m2": section.area_m2,
                "shear_area_y_m2": section.shear_area_y_m2,
                "shear_area_z_m2": section.shear_area_z_m2,
                "ixx_m4": section.ixx_m4, "iyy_m4": section.iyy_m4,
                "izz_m4": section.izz_m4,
                "elastic_modulus_pa": section.elastic_modulus_pa,
                "shear_modulus_pa": section.shear_modulus_pa,
                "poisson_ratio": section.poisson_ratio,
                "density_kg_m3": section.density_kg_m3,
                "max_axial_n": section.max_axial_n,
                "max_shear_y_n": section.max_shear_y_n,
                "max_shear_z_n": section.max_shear_z_n,
                "max_torsion_nm": section.max_torsion_nm,
                "max_moment_y_nm": section.max_moment_y_nm,
                "max_moment_z_nm": section.max_moment_z_nm,
                "source_path": section.source_path,
                "material_source_path": section.material_source_path,
            }
        row["issues"] = sorted(set(
            row["issues"] + truss.cross_section_issues))
    with open(section_path, "w", encoding="utf-8") as stream:
        json.dump({"cross_sections": list(section_rows.values())}, stream,
                  ensure_ascii=False, indent=2)
    if progress:
        progress("update", 4, "Model reports complete 4/4")
        progress("start", len(constructions),
                 "Linear analysis 0/{}".format(len(constructions)))

    def linear_progress(construction_id, completed, total):
        if progress:
            progress("update", completed, "Linear analysis {}/{}: {}".format(
                completed, total, construction_id))

    calculation = calculate_reactions(
        document, constructions, progress=linear_progress)
    calculation_json_path = os.path.join(output_dir, "rigcalc_calculation.json")
    calculation_text_path = os.path.join(output_dir, "rigcalc_calculation.txt")
    with open(calculation_json_path, "w", encoding="utf-8") as stream:
        json.dump(calculation, stream, ensure_ascii=False, indent=2)
    with open(calculation_text_path, "w", encoding="utf-8") as stream:
        stream.write(make_calculation_text(calculation))
    if progress:
        progress("start", len(constructions),
                 "Nonlinear analysis 0/{}".format(len(constructions)))
    nonlinear_completed = set()

    def nonlinear_progress(construction_id, state):
        if not progress:
            return
        if state.get("completed"):
            nonlinear_completed.add(construction_id)
            progress("update", len(nonlinear_completed),
                     "Nonlinear analysis {}/{}: {} complete".format(
                         len(nonlinear_completed), len(constructions),
                         construction_id))
        else:
            progress("pulse", message=(
                "{}: load {:.1f}%, iteration {}".format(
                    construction_id, 100.0*state["load_factor"],
                    state["iteration"])))

    nonlinear = calculate_corotational_reactions(
        document, constructions, progress=nonlinear_progress)
    if progress:
        progress("start", 4, "Writing results 0/4")
    nonlinear_json_path = os.path.join(
        output_dir, "rigcalc_nonlinear_calculation.json")
    nonlinear_text_path = os.path.join(
        output_dir, "rigcalc_nonlinear_calculation.txt")
    with open(nonlinear_json_path, "w", encoding="utf-8") as stream:
        json.dump(nonlinear, stream, ensure_ascii=False, indent=2)
    with open(nonlinear_text_path, "w", encoding="utf-8") as stream:
        stream.write(make_calculation_text(nonlinear))
    comparison = compare_calculations(calculation, nonlinear)
    with open(os.path.join(output_dir, "rigcalc_solver_comparison.json"),
              "w", encoding="utf-8") as stream:
        json.dump(comparison, stream, ensure_ascii=False, indent=2)
    with open(os.path.join(output_dir, "rigcalc_solver_comparison.txt"),
              "w", encoding="utf-8") as stream:
        stream.write(make_comparison_text(comparison))
    primary = select_primary_calculation(calculation, nonlinear)
    with open(os.path.join(output_dir, "rigcalc_primary_calculation.json"),
              "w", encoding="utf-8") as stream:
        json.dump(primary, stream, ensure_ascii=False, indent=2)
    with open(os.path.join(output_dir, "rigcalc_primary_calculation.txt"),
              "w", encoding="utf-8") as stream:
        stream.write(make_calculation_text(primary))
    hoist_outcomes = build_hoist_outcomes(document, primary)
    with open(os.path.join(output_dir, "rigcalc_hoist_outcomes.json"),
              "w", encoding="utf-8") as stream:
        json.dump({"hoist_outcomes": hoist_outcomes}, stream,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(output_dir, "rigcalc_hoist_outcomes.txt"),
              "w", encoding="utf-8") as stream:
        stream.write(make_hoist_outcomes_text(hoist_outcomes))
    notifications = (evaluate_notifications(primary) +
                     evaluate_zero_hoist_outcomes(hoist_outcomes))
    with open(os.path.join(output_dir, "rigcalc_notifications.json"),
              "w", encoding="utf-8") as stream:
        json.dump({"notifications": notifications}, stream,
                  ensure_ascii=False, indent=2)
    notification_writeback = write_notification_markers(
        vs, document, constructions, notifications)
    with open(os.path.join(output_dir, "rigcalc_notification_writeback.json"),
              "w", encoding="utf-8") as stream:
        json.dump(notification_writeback, stream,
                  ensure_ascii=False, indent=2)
    if progress:
        progress("update", 2, "Reports written 2/4")
    writeback = write_high_hook_values(
        vs, document, primary, confirm=False)
    writeback_path = os.path.join(output_dir, "rigcalc_writeback.json")
    with open(writeback_path, "w", encoding="utf-8") as stream:
        json.dump(writeback, stream, ensure_ascii=False, indent=2)
    if progress:
        progress("update", 3, "High Hook fields written 3/4")
    cross_writeback = write_truss_cross_forces(
        vs, document, primary, confirm=False)
    cross_writeback_path = os.path.join(
        output_dir, "rigcalc_truss_cross_writeback.json")
    with open(cross_writeback_path, "w", encoding="utf-8") as stream:
        json.dump(cross_writeback, stream, ensure_ascii=False, indent=2)
    if progress:
        progress("update", 4, "Complete 4/4")
        progress("close")
    summary = build_run_summary(
        document, constructions, primary, writeback, cross_writeback,
        hoist_id_assignment=hoist_id_assignment,
        notifications=notifications, hoist_outcomes=hoist_outcomes)
    with open(os.path.join(output_dir, "rigcalc_run_summary.json"),
              "w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    show_run_summary_dialog(vs, summary)
    return text_path, json_path
