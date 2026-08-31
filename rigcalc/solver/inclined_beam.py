"""Diagnostic linear frame adapter for straight inclined truss chains."""

from .beam_statics import _reaction_record
from .continuous_beam import (GRAVITY_M_S2, MAX_EXHAUSTIVE_TENSION_ONLY_HOISTS,
                              STATION_TOLERANCE_MM, _section_at)
from .frame3d import (FrameElement, FrameModel, FrameNode, element_axes,
                      global_uniform_load_to_local, solve_frame)
from .inclined_geometry import inclined_station_coordinates, planar_coordinate
from .contact import contact_mass_by_support, engaged_contact_mass_loads
from math import sqrt
from itertools import combinations
from .deflection import build_deflection_summary, support_span_midpoints


def solve_inclined_planar_frame(construction, loads, _active_ids=None,
                                _signed_reactions=None):
    all_supports = sorted((item for item in construction.supports
                       if item.attachment.global_station_mm is not None),
                      key=lambda item: item.attachment.global_station_mm)
    supports = [item for item in all_supports
                if _active_ids is None or item.item.id in _active_ids]
    result = {"construction_id": construction.id, "construction_name": construction.label,
              "status": "not_calculated", "method": "inclined_planar_3d_frame_diagnostic",
              "loads": loads, "writeback_eligible": False, "load_transfer_eligible": False,
              "total_applied_mass_kg": sum(item["mass_kg"] for item in loads),
              "reactions": [], "stations": [], "issues": []}
    coordinates, issue = inclined_station_coordinates(construction)
    if issue:
        result["issues"].append(issue); return result
    if len(supports) < 2 or not loads:
        result["issues"].append("requires_two_or_more_distinct_supports"); return result
    support_stations = [item.attachment.global_station_mm for item in supports]
    stations = sorted(set(coordinates) | {item.attachment.global_station_mm for item in all_supports} |
                      set(support_span_midpoints(support_stations)) |
                      {item["station_mm"] for item in loads})
    nodes = []
    for index, station in enumerate(stations):
        x, z = planar_coordinate(station, coordinates)
        if x is None or z is None:
            result["issues"].append("unsupported_partial_inclined_station"); return result
        supported = any(abs(item.attachment.global_station_mm-station) <= STATION_TOLERANCE_MM for item in supports)
        force = -sum(item["mass_kg"]*GRAVITY_M_S2 for item in loads
                     if "interval_start_mm" not in item and abs(item["station_mm"]-station) <= STATION_TOLERANCE_MM)
        nodes.append(FrameNode("N{:04d}".format(index), x/1000.0, 0.0, z/1000.0,
                               restrained=(index == 0, True, supported, True, False, True),
                               load=(0, 0, force, 0, 0, 0)))
    elements = []
    for index, (start, end) in enumerate(zip(stations, stations[1:])):
        section = _section_at(construction, (start+end)/2)
        if section is None:
            result["issues"].append("mechanical_section_missing_at_{:.3f}_mm".format((start+end)/2)); return result
        q_global = (0.0, 0.0, 0.0)
        for load in loads:
            if "interval_start_mm" in load and start >= load["interval_start_mm"]-1e-6 and end <= load["interval_end_mm"]+1e-6:
                physical_length_m = sum(
                    sqrt((nodes[j+1].x-nodes[j].x)**2 +
                         (nodes[j+1].z-nodes[j].z)**2)
                    for j, (first, last) in enumerate(zip(stations, stations[1:]))
                    if first >= load["interval_start_mm"]-1e-6 and
                    last <= load["interval_end_mm"]+1e-6)
                if physical_length_m > 0.0:
                    q_global = (0.0, 0.0, q_global[2]-load["mass_kg"]*
                                GRAVITY_M_S2/physical_length_m)
        element = FrameElement("E{:04d}".format(index), nodes[index].id, nodes[index+1].id,
            section.elastic_modulus_pa, section.shear_modulus_pa, section.area_m2, section.ixx_m4, section.iyy_m4, section.izz_m4)
        element.uniform_local_load_n_m = global_uniform_load_to_local(q_global, element_axes(nodes[index], nodes[index+1], element.reference_vector))
        elements.append(element)
    try:
        solved = solve_frame(FrameModel(nodes, elements))
    except ValueError as error:
        result["issues"].append(str(error)); return result
    result["numerical_diagnostics"] = solved["numerical_diagnostics"]
    for support in supports:
        node = next(node for node, station in zip(nodes, stations) if abs(station-support.attachment.global_station_mm) <= STATION_TOLERANCE_MM)
        result["reactions"].append(_reaction_record(support, solved["node_reactions"][node.id][2]/GRAVITY_M_S2))
    contact_masses = contact_mass_by_support(loads)
    for reaction in result["reactions"]:
        mass = contact_masses.get(reaction["support_id"], 0.0)
        if mass:
            reaction["contact_mass_included_kg"] = mass
            # This reaction already includes the contact load, so it cannot
            # also receive the chain mass through the ordinary High Hook path.
            reaction["preliminary_high_hook_mass_kg"] = reaction["reaction_mass_kg"]
            reaction["high_hook_mass_basis"] = (
                "reaction_includes_engaged_contact_mass_diagnostic")
    if _signed_reactions is None:
        _signed_reactions = [dict(item) for item in result["reactions"]]
    if _active_ids is None:
        hoists = [item for item in all_supports if not item.item.is_structural_link]
        if len(hoists) <= MAX_EXHAUSTIVE_TENSION_ONLY_HOISTS:
            valid = []
            for size in range(len(hoists)+1):
                for chosen in combinations(hoists, size):
                    ids = {item.item.id for item in chosen} | {item.item.id for item in all_supports if item.item.is_structural_link}
                    if len(ids) < 2: continue
                    candidate_loads = list(loads) + engaged_contact_mass_loads(chosen)
                    candidate = solve_inclined_planar_frame(construction, candidate_loads, ids, _signed_reactions)
                    if candidate["status"] != "diagnostic" or any(r["reaction_mass_kg"] < -1e-6 for r in candidate["reactions"]): continue
                    displacement = {round(item["station_mm"], 6): item["displacements"]["uz_m"] for item in candidate["stations"]}
                    if any(displacement[round(item.attachment.global_station_mm, 6)] > 1e-8 for item in hoists if item.item.id not in ids): continue
                    valid.append(candidate)
            if valid:
                result = max(valid, key=lambda item: len(item["reactions"]))
                active = {item["support_id"]: item for item in result["reactions"]}
                signed = {item["support_id"]: item for item in _signed_reactions}
                result["reactions"] = []
                for support in all_supports:
                    reaction = active.get(support.item.id, _reaction_record(support, 0.0))
                    reaction["support_active"] = support.item.id in active
                    reaction["unconstrained_reaction_mass_kg"] = signed.get(support.item.id, {}).get("reaction_mass_kg")
                    result["reactions"].append(reaction)
                result["active_set_validation"] = {"method":"exhaustive_inclined_tension_only_active_set", "candidate_sets_valid":len(valid)}
                return result
            # A negative reaction is a cable-slack condition, not an allowable
            # hoist load.  Do not present the unconstrained linear result as a
            # usable support model when no subset of the fixed support points
            # satisfies the unilateral (tension-only) constraints.
            result["active_set_validation"] = {
                "method": "exhaustive_inclined_tension_only_active_set",
                "candidate_sets_valid": 0,
            }
            result["issues"].append(
                "tension_only_active_set_no_feasible_solution"
            )
            for reaction in result["reactions"]:
                reaction["support_active"] = True
                reaction["unconstrained_reaction_mass_kg"] = reaction["reaction_mass_kg"]
        else:
            result["active_set_validation"] = {
                "method": "not_enumerated_inclined_tension_only_active_set",
                "maximum_exhaustive_hoists": MAX_EXHAUSTIVE_TENSION_ONLY_HOISTS,
                "hoist_count": len(hoists),
            }
            result["issues"].append("tension_only_active_set_limit_exceeded")
    result["stations"] = [{"node_id": node.id, "station_mm": station,
                           "displacements": dict(zip(("ux_m", "uy_m", "uz_m", "rx_rad", "ry_rad", "rz_rad"), solved["node_displacements"][node.id]))}
                          for node, station in zip(nodes, stations)]
    reaction_total = sum(item["reaction_mass_kg"] for item in result["reactions"])
    applied_moment = sum(item["mass_kg"] * planar_coordinate(
        item["station_mm"], coordinates)[0] / 1000.0 for item in loads)
    reaction_moment = sum(item["reaction_mass_kg"] * planar_coordinate(
        item["station_mm"], coordinates)[0] / 1000.0
                          for item in result["reactions"])
    result["validation"] = {
        "vertical_equilibrium_error_kg": reaction_total-result["total_applied_mass_kg"],
        "vertical_equilibrium_ok": abs(reaction_total-result["total_applied_mass_kg"]) <= 0.01,
        "moment_equilibrium_error_kg_m": reaction_moment-applied_moment,
        "moment_equilibrium_ok": abs(reaction_moment-applied_moment) <= 0.01,
        "support_model_valid": False,
        "numerically_valid": (
            result["numerical_diagnostics"]["relative_reduced_residual"]
            <= 1.0e-8),
        "load_model_valid": True,
    }
    result["deflection"] = build_deflection_summary(
        result["stations"], support_stations)
    result["status"] = "diagnostic"
    result["issues"].append("inclined_geometry_diagnostic_not_writeback_source")
    if contact_masses:
        result["issues"].append(
            "tension_only_contact_model_diagnostic_not_writeback_source")
    else:
        result["issues"].append("tension_only_contact_mass_model_not_implemented")
    return result
