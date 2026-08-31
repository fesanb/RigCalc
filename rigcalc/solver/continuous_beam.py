"""General linear continuous-beam adapter for open truss chains.

The adapter accepts any number and spacing of vertical supports. It embeds the
beam in the general 3D frame solver while suppressing unrelated rigid-body DOF.
The unconstrained signed solution is retained for diagnostics. Hoists are then
treated as tension-only supports: a hoist requiring a downward reaction is
released and the model is solved again. Structural links remain bilateral.

This remains a first-order vertical model, not the later geometric model.
"""

from itertools import combinations

from .beam_statics import _reaction_record, planar_beam_geometry_issue
from .deflection import (build_deflection_summary,
                         support_span_midpoints)
from .frame3d import FrameElement, FrameModel, FrameNode, solve_frame
from .validation import finalize_eligibility


GRAVITY_M_S2 = 9.80665
STATION_TOLERANCE_MM = 1.0e-6
MAX_EXHAUSTIVE_TENSION_ONLY_HOISTS = 8


def _unique_stations(values):
    result = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > STATION_TOLERANCE_MM:
            result.append(value)
    return result


def _section_at(construction, station_mm):
    for truss in construction.truss_segments:
        span = construction.station_map.get(truss.id)
        if span is None:
            continue
        low = min(span.start_station_mm, span.end_station_mm)
        high = max(span.start_station_mm, span.end_station_mm)
        if low-STATION_TOLERANCE_MM <= station_mm <= high+STATION_TOLERANCE_MM:
            return truss.mechanical_section
    return None


def _support_at(supports, station_mm):
    for support in supports:
        if abs(support.attachment.global_station_mm-station_mm) <= STATION_TOLERANCE_MM:
            return support
    return None


def _section_result(section):
    return {
        "identifier": section.identifier,
        "capacities": {
            "N_n": section.max_axial_n,
            "Vy_n": section.max_shear_y_n,
            "Vz_n": section.max_shear_z_n,
            "T_nm": section.max_torsion_nm,
            "My_nm": section.max_moment_y_nm,
            "Mz_nm": section.max_moment_z_nm,
        },
    }


def _resolve_tension_only_active_set(construction, loads, signed_reactions):
    """Find the complementarity-valid hoist set for a small support system.

    A released cable must have non-positive vertical displacement (slack/down),
    while every active cable must have a non-negative reaction.  Enumerating
    the candidate sets avoids the unsafe assumption that a released support
    can never become active again after load redistribution.
    """
    supports = [item for item in construction.supports
                if item.attachment.global_station_mm is not None]
    hoists = [item for item in supports if not item.item.is_structural_link]
    if len(hoists) > MAX_EXHAUSTIVE_TENSION_ONLY_HOISTS:
        if all(item["reaction_mass_kg"] >= -1.0e-6
               for item in signed_reactions
               if not item["is_structural_link"]):
            return "all_active_nonnegative", None
        return "limit_exceeded", None
    structural_ids = {item.item.id for item in supports
                      if item.item.is_structural_link}
    candidates, evaluated = [], 0
    for count in range(len(hoists)+1):
        for active_hoists in combinations(hoists, count):
            active_ids = structural_ids | {item.item.id for item in active_hoists}
            if len(active_ids) < 2:
                continue
            evaluated += 1
            candidate = solve_continuous_beam(
                construction, loads, _active_support_ids=active_ids,
                _signed_reactions=signed_reactions,
                _resolve_tension_only=False)
            if candidate["status"] != "preliminary":
                continue
            reactions = {item["support_id"]: item
                         for item in candidate["reactions"]}
            active_valid = all(
                reactions[item.item.id]["reaction_mass_kg"] >= -1.0e-6
                for item in active_hoists)
            displacements = {
                round(item["station_mm"], 6): item["displacements"]["uz_m"]
                for item in candidate["stations"]}
            released_valid = all(
                displacements.get(round(item.attachment.global_station_mm, 6),
                                  float("inf")) <= 1.0e-8
                for item in hoists if item not in active_hoists)
            if active_valid and released_valid:
                candidates.append((len(active_hoists), candidate))
    if not candidates:
        return "no_feasible_solution", None
    # Prefer the valid contact set with the most engaged hoists. This is also
    # deterministic in degenerate zero-reaction cases.
    result = max(candidates, key=lambda item: item[0])[1]
    result["active_set_validation"] = {
        "method": "exhaustive_tension_only_active_set",
        "candidate_sets_evaluated": evaluated,
        "candidate_sets_valid": len(candidates),
        "released_support_displacement_rule": "uz_m <= 1e-8",
    }
    return "resolved", result


def solve_continuous_beam(construction, loads, _active_support_ids=None,
                          _signed_reactions=None,
                          _resolve_tension_only=True):
    all_supports = sorted(
        (item for item in construction.supports
         if item.attachment.global_station_mm is not None),
        key=lambda item: item.attachment.global_station_mm)
    supports = [item for item in all_supports
                if (_active_support_ids is None or
                    item.item.id in _active_support_ids)]
    result = {
        "construction_id": construction.id,
        "construction_name": construction.label,
        "status": "not_calculated",
        "method": None, "loads": loads,
        "writeback_eligible": False,
        "load_transfer_eligible": False,
        "total_applied_mass_kg": sum(item["mass_kg"] for item in loads),
        "reactions": [], "stations": [], "element_forces": [],
        "node_displacements": {},
        "issues": [],
    }
    all_support_stations = _unique_stations(
        [item.attachment.global_station_mm for item in all_supports])
    support_stations = _unique_stations(
        [item.attachment.global_station_mm for item in supports])
    geometry_issue = planar_beam_geometry_issue(construction)
    if geometry_issue:
        result["issues"].append(geometry_issue)
        return result
    if construction.stationing != "open_chain":
        result["issues"].append("requires_branched_or_loop_solver")
        return result
    if (len(all_supports) < 2 or
            len(all_support_stations) != len(all_supports) or
            len(supports) < 2 or len(support_stations) != len(supports)):
        result["issues"].append("requires_two_or_more_distinct_supports")
        return result
    if not loads:
        result["issues"].append("no_applied_loads")
        return result
    span_end = max(
        [construction.nominal_truss_length_mm] +
        [max(item.start_station_mm, item.end_station_mm)
         for item in construction.station_map.values()])
    stations = ([0.0, span_end] + all_support_stations +
                support_span_midpoints(support_stations))
    for span in construction.station_map.values():
        stations.extend((span.start_station_mm, span.end_station_mm))
    for load in loads:
        if "interval_start_mm" in load:
            stations.extend((max(0.0, load["interval_start_mm"]),
                             min(span_end, load["interval_end_mm"])))
        else:
            stations.append(load["station_mm"])
    stations = _unique_stations(stations)
    nodes = []
    for index, station in enumerate(stations):
        support = _support_at(supports, station)
        # uy/rx/rz remove unused lateral/torsional rigid modes. ux is fixed at
        # one node only; support nodes restrain vertical uz and leave ry free.
        restrained = (index == 0, True, support is not None, True, False, True)
        point_force_n = -sum(
            load["mass_kg"] * GRAVITY_M_S2 for load in loads
            if "interval_start_mm" not in load and
            abs(load["station_mm"]-station) <= STATION_TOLERANCE_MM)
        nodes.append(FrameNode(
            "N{:04d}".format(index), station/1000.0, 0.0, 0.0,
            restrained=restrained,
            load=(0.0, 0.0, point_force_n, 0.0, 0.0, 0.0)))
    elements = []
    element_sections = {}
    for index, (start, end) in enumerate(zip(stations, stations[1:])):
        midpoint = (start+end)/2.0
        section = _section_at(construction, midpoint)
        if section is None:
            result["issues"].append(
                "mechanical_section_missing_at_{:.3f}_mm".format(midpoint))
            return result
        required = (section.elastic_modulus_pa, section.shear_modulus_pa,
                    section.area_m2, section.ixx_m4,
                    section.iyy_m4, section.izz_m4)
        if any(value is None or value <= 0.0 for value in required):
            result["issues"].append(
                "mechanical_section_incomplete:{}".format(section.identifier))
            return result
        uniform_mass_kg_m = 0.0
        for load in loads:
            if "interval_start_mm" not in load:
                continue
            interval_start, interval_end = (
                load["interval_start_mm"], load["interval_end_mm"])
            if start >= interval_start-STATION_TOLERANCE_MM and end <= interval_end+STATION_TOLERANCE_MM:
                interval_m = (interval_end-interval_start)/1000.0
                if interval_m > 0.0:
                    uniform_mass_kg_m += load["mass_kg"] / interval_m
        element_id = "E{:04d}".format(index)
        elements.append(FrameElement(
            element_id, nodes[index].id, nodes[index+1].id,
            section.elastic_modulus_pa, section.shear_modulus_pa,
            section.area_m2, section.ixx_m4, section.iyy_m4,
            section.izz_m4,
            uniform_local_load_n_m=(0.0, 0.0,
                                    -uniform_mass_kg_m*GRAVITY_M_S2)))
        element_sections[element_id] = _section_result(section)
    try:
        frame_result = solve_frame(FrameModel(nodes, elements))
    except ValueError as error:
        result["issues"].append(str(error))
        return result
    node_by_station = {station: nodes[index].id
                       for index, station in enumerate(stations)}
    for support in supports:
        station = support.attachment.global_station_mm
        node_id = next(node_by_station[value] for value in node_by_station
                       if abs(value-station) <= STATION_TOLERANCE_MM)
        reaction_n = frame_result["node_reactions"][node_id][2]
        result["reactions"].append(
            _reaction_record(support, reaction_n/GRAVITY_M_S2))
    if _signed_reactions is None:
        _signed_reactions = [dict(item) for item in result["reactions"]]
    active_set_issue = None
    if _resolve_tension_only and _active_support_ids is None:
        active_set_state, active_set_result = _resolve_tension_only_active_set(
            construction, loads, _signed_reactions)
        if active_set_state == "resolved":
            return active_set_result
        if active_set_state != "all_active_nonnegative":
            active_set_issue = {
                "no_feasible_solution": "tension_only_active_set_no_feasible_solution",
                "limit_exceeded": "tension_only_active_set_limit_exceeded",
            }[active_set_state]
    negative_hoists = [
        item for item in result["reactions"]
        if item["reaction_mass_kg"] < -1.0e-6 and
        not item["is_structural_link"]]
    active_reactions = {
        item["support_id"]: item for item in result["reactions"]}

    # Once tension-only releases leave exactly two active supports, force and
    # moment equilibrium define the reactions directly.  Replacing the two
    # numerically recovered frame reactions removes solver round-off without
    # relaxing either validation tolerance.
    equilibrium_correction = None
    if len(supports) == 2 and not negative_hoists:
        left, right = sorted(
            supports, key=lambda item: item.attachment.global_station_mm)
        a = left.attachment.global_station_mm
        b = right.attachment.global_station_mm
        if b-a > STATION_TOLERANCE_MM:
            right_mass = sum(
                load["mass_kg"]*(load["station_mm"]-a)/(b-a)
                for load in loads)
            exact = {
                left.item.id: result["total_applied_mass_kg"]-right_mass,
                right.item.id: right_mass,
            }
            if min(exact.values()) >= -1.0e-6:
                largest_change = 0.0
                for support_id, mass in exact.items():
                    reaction = active_reactions[support_id]
                    largest_change = max(
                        largest_change,
                        abs(mass-reaction["reaction_mass_kg"]))
                    reaction["reaction_mass_kg"] = mass
                    reaction["preliminary_high_hook_mass_kg"] = (
                        mass+reaction["hoist_and_chain_mass_kg"])
                equilibrium_correction = {
                    "method": "two_active_support_static_equilibrium",
                    "maximum_reaction_adjustment_kg": largest_change,
                }
    signed_lookup = {
        item["support_id"]: item for item in _signed_reactions}
    result["reactions"] = []
    for support in all_supports:
        reaction = active_reactions.get(support.item.id)
        if reaction is None:
            reaction = _reaction_record(support, 0.0)
            reaction["support_active"] = False
        else:
            reaction["support_active"] = True
        signed = signed_lookup.get(support.item.id)
        reaction["unconstrained_reaction_mass_kg"] = (
            signed["reaction_mass_kg"] if signed else None)
        result["reactions"].append(reaction)
    result["signed_reactions"] = _signed_reactions
    reaction_total = sum(
        item["reaction_mass_kg"] for item in result["reactions"])
    equilibrium_error = reaction_total-result["total_applied_mass_kg"]
    equilibrium_tolerance = max(
        0.01, abs(result["total_applied_mass_kg"])*1.0e-6)
    applied_moment_kg_m = sum(
        item["mass_kg"]*item["station_mm"]/1000.0 for item in loads)
    reaction_moment_kg_m = sum(
        item["reaction_mass_kg"]*item["station_mm"]/1000.0
        for item in result["reactions"])
    moment_error = reaction_moment_kg_m-applied_moment_kg_m
    moment_tolerance = max(
        0.01, abs(applied_moment_kg_m)*1.0e-6)
    result["validation"] = {
        "vertical_equilibrium_error_kg": equilibrium_error,
        "vertical_equilibrium_tolerance_kg": equilibrium_tolerance,
        "vertical_equilibrium_ok": abs(equilibrium_error) <= equilibrium_tolerance,
        "moment_equilibrium_error_kg_m": moment_error,
        "moment_equilibrium_tolerance_kg_m": moment_tolerance,
        "moment_equilibrium_ok": abs(moment_error) <= moment_tolerance,
    }
    if equilibrium_correction is not None:
        result["validation"]["reaction_equilibrium_correction"] = (
            equilibrium_correction)
    force_labels = ("N_n", "Vy_n", "Vz_n", "T_nm", "My_nm", "Mz_nm")
    station_by_node = {node.id: station for node, station in zip(nodes, stations)}
    result["element_forces"] = []
    for item in frame_result["element_results"]:
        values = item["local_end_forces"]
        result["element_forces"].append({
            "element_id": item["element_id"],
            "start_station_mm": station_by_node[item["node_i"]],
            "end_station_mm": station_by_node[item["node_j"]],
            "length_m": item["length_m"],
            "cross_section": element_sections[item["element_id"]],
            "i": dict(zip(force_labels, values[:6])),
            "j": dict(zip(force_labels, values[6:])),
        })
    result["node_displacements"] = frame_result["node_displacements"]
    result["numerical_diagnostics"] = frame_result["numerical_diagnostics"]
    displacement_labels = ("ux_m", "uy_m", "uz_m", "rx_rad", "ry_rad", "rz_rad")
    for node, station in zip(nodes, stations):
        result["stations"].append({
            "node_id": node.id,
            "station_mm": station,
            "displacements": dict(zip(
                displacement_labels,
                frame_result["node_displacements"][node.id])),
        })
    result["deflection"] = build_deflection_summary(
        result["stations"], support_stations)
    result["status"] = "preliminary"
    result["method"] = "linear_planar_continuous_beam_vertical_supports"
    if active_set_issue:
        result["issues"].append(active_set_issue)
        result["status"] = "diagnostic"
    elif _resolve_tension_only and _active_support_ids is None:
        result["active_set_validation"] = {
            "method": "all_active_hoists_nonnegative",
            "candidate_sets_evaluated": 1,
        }
    contact_mass_model_missing = any(
        not item["is_structural_link"] for item in result["reactions"])
    if contact_mass_model_missing:
        # A fixed-point active set preserves a valuable signed diagnostic, but
        # it is not the physical cable-contact solution until slack,
        # re-engagement and hoist/chain mass are represented at contact.
        result["issues"].append(
            "tension_only_contact_mass_model_not_implemented")
    finalize_eligibility(
        result, support_model_valid=(not negative_hoists and
                                     active_set_issue is None and
                                     not contact_mass_model_missing),
        numerical_valid=(result["numerical_diagnostics"]
                         ["relative_reduced_residual"] <= 1.0e-8))
    released_count = sum(
        not item["support_active"] for item in result["reactions"])
    if released_count:
        result["method"] = "linear_planar_continuous_beam_tension_only_hoists"
        result["active_support_count"] = len(all_supports)-released_count
        result["released_support_count"] = released_count
    result["issues"].append("first_order_vertical_support_model")
    return result
