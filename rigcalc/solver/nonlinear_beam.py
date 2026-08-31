"""Adapter from RigCalc constructions to the corotational 2D solver."""

from .beam_statics import (_reaction_record, planar_beam_geometry_issue,
                           trace_construction_loads)
from .continuous_beam import (GRAVITY_M_S2, STATION_TOLERANCE_MM,
                              _section_at, _section_result, _support_at,
                              _unique_stations)
from .deflection import (build_deflection_summary,
                         support_span_midpoints)
from .corotational import (CorotationalElement, CorotationalModel,
                           CorotationalNode, solve_corotational)
from .validation import finalize_eligibility


def solve_corotational_beam(construction, loads, progress=None):
    supports = sorted(
        (item for item in construction.supports
         if item.attachment.global_station_mm is not None),
        key=lambda item: item.attachment.global_station_mm)
    result = {
        "construction_id": construction.id,
        "construction_name": construction.label,
        "status": "not_calculated",
        "method": "corotational_2d_frame", "loads": loads,
        "writeback_eligible": False,
        "load_transfer_eligible": False,
        "load_model": {
            "direction": "fixed_global_negative_z",
            "reference_configuration": "undeformed_station_geometry",
            "distributed_load": "equivalent_nodal_gravity_load_not_follower",
        },
        "total_applied_mass_kg": sum(item["mass_kg"] for item in loads),
        "reactions": [], "stations": [], "element_forces": [], "issues": [],
    }
    support_stations = _unique_stations(
        [item.attachment.global_station_mm for item in supports])
    geometry_issue = planar_beam_geometry_issue(construction)
    if geometry_issue:
        # Straight inclined chains use a dedicated corotational diagnostic
        # adapter. Other geometry failures remain explicit in that adapter.
        from .inclined_corotational import solve_inclined_corotational_beam
        return solve_inclined_corotational_beam(
            construction, loads)
    if construction.stationing != "open_chain":
        result["issues"].append("requires_open_chain")
        return result
    if len(supports) < 2 or len(support_stations) != len(supports):
        result["issues"].append("requires_two_or_more_distinct_supports")
        return result
    if not loads:
        result["issues"].append("no_applied_loads")
        return result
    span_end = max(
        [construction.nominal_truss_length_mm] +
        [max(item.start_station_mm, item.end_station_mm)
         for item in construction.station_map.values()])
    stations = ([0.0, span_end] + support_stations +
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
    node_loads = [[0.0, 0.0, 0.0] for _ in stations]
    for index, station in enumerate(stations):
        node_loads[index][1] -= sum(
            load["mass_kg"]*GRAVITY_M_S2 for load in loads
            if "interval_start_mm" not in load and
            abs(load["station_mm"]-station) <= STATION_TOLERANCE_MM)
    elements = []
    element_sections = {}
    for index, (start, end) in enumerate(zip(stations, stations[1:])):
        section = _section_at(construction, (start+end)/2.0)
        if section is None:
            result["issues"].append(
                "mechanical_section_missing_at_{:.3f}_mm".format((start+end)/2))
            return result
        required = (section.elastic_modulus_pa, section.area_m2,
                    section.iyy_m4)
        if any(value is None or value <= 0.0 for value in required):
            result["issues"].append(
                "mechanical_section_incomplete:{}".format(section.identifier))
            return result
        length_m = (end-start)/1000.0
        uniform_mass = 0.0
        for load in loads:
            if "interval_start_mm" not in load:
                continue
            if (start >= load["interval_start_mm"]-STATION_TOLERANCE_MM and
                    end <= load["interval_end_mm"]+STATION_TOLERANCE_MM):
                interval_m = (load["interval_end_mm"]-
                              load["interval_start_mm"])/1000.0
                if interval_m > 0.0:
                    uniform_mass += load["mass_kg"]/interval_m
        qz = -uniform_mass*GRAVITY_M_S2
        node_loads[index][1] += qz*length_m/2.0
        node_loads[index+1][1] += qz*length_m/2.0
        node_loads[index][2] += -qz*length_m**2/12.0
        node_loads[index+1][2] += qz*length_m**2/12.0
        element_id = "E{:04d}".format(index)
        elements.append(CorotationalElement(
            element_id, "N{:04d}".format(index),
            "N{:04d}".format(index+1), section.elastic_modulus_pa,
            section.area_m2, section.iyy_m4))
        element_sections[element_id] = _section_result(section)
    anchor_station = support_stations[0]
    nodes = []
    for index, station in enumerate(stations):
        is_support = _support_at(supports, station) is not None
        nodes.append(CorotationalNode(
            "N{:04d}".format(index), station/1000.0, 0.0,
            restrained=(abs(station-anchor_station) <= STATION_TOLERANCE_MM,
                        is_support, False),
            load=tuple(node_loads[index])))
    try:
        solved = solve_corotational(
            CorotationalModel(nodes, elements), progress=progress)
    except ValueError as error:
        result["issues"].append(str(error))
        return result
    result["converged"] = solved["converged"]
    result["iterations"] = solved["iterations"]
    result["completed_load_factor"] = solved["completed_load_factor"]
    result["load_history"] = solved["load_history"]
    for support in supports:
        station = support.attachment.global_station_mm
        index = next(index for index, value in enumerate(stations)
                     if abs(value-station) <= STATION_TOLERANCE_MM)
        reaction_n = solved["node_reactions"][nodes[index].id][1]
        result["reactions"].append(
            _reaction_record(support, reaction_n/GRAVITY_M_S2))
    for node, station in zip(nodes, stations):
        ux, uz, rotation = solved["node_displacements"][node.id]
        result["stations"].append({
            "node_id": node.id, "station_mm": station,
            "displacements": {
                "ux_m": ux, "uy_m": 0.0, "uz_m": uz,
                "rx_rad": 0.0, "ry_rad": rotation, "rz_rad": 0.0,
            },
        })
    result["deflection"] = build_deflection_summary(
        result["stations"], support_stations)
    station_by_node = {node.id: station for node, station in zip(nodes, stations)}
    for element in solved["element_results"]:
        result["element_forces"].append({
            "element_id": element["element_id"],
            "start_station_mm": station_by_node[element["node_i"]],
            "end_station_mm": station_by_node[element["node_j"]],
            "length_m": element["length_m"],
            "cross_section": element_sections[element["element_id"]],
            "i": element["i"], "j": element["j"],
        })
    error = (sum(item["reaction_mass_kg"] for item in result["reactions"])-
             result["total_applied_mass_kg"])
    tolerance = max(1.0e-5, abs(result["total_applied_mass_kg"])*1.0e-7)
    moment_residual_n_m = 0.0
    moment_reference_n_m = 0.0
    factor = solved["completed_load_factor"]
    for node in nodes:
        ux, uz, _ = solved["node_displacements"][node.id]
        reaction = solved["node_reactions"][node.id]
        applied = [factor*value for value in node.load]
        x, z = node.x+ux, node.z+uz
        applied_moment = x*applied[1]-z*applied[0]+applied[2]
        reaction_moment = x*reaction[1]-z*reaction[0]+reaction[2]
        moment_residual_n_m += applied_moment+reaction_moment
        moment_reference_n_m += abs(applied_moment)+abs(reaction_moment)
    moment_error = moment_residual_n_m/GRAVITY_M_S2
    moment_tolerance = max(
        0.01, moment_reference_n_m/GRAVITY_M_S2*1.0e-6)
    result["validation"] = {
        "vertical_equilibrium_error_kg": error,
        "vertical_equilibrium_tolerance_kg": tolerance,
        "vertical_equilibrium_ok": abs(error) <= tolerance,
        "moment_equilibrium_error_kg_m": moment_error,
        "moment_equilibrium_tolerance_kg_m": moment_tolerance,
        "moment_equilibrium_ok": abs(moment_error) <= moment_tolerance,
    }
    if solved["converged"]:
        result["status"] = "diagnostic"
    else:
        result["issues"].append("nonlinear_solution_did_not_converge")
    result["issues"].append("diagnostic_not_writeback_source")
    # Vertical supports are bilateral in this solver. Its signed reactions
    # remain useful diagnostics, but cannot certify a tension-only hoist model.
    finalize_eligibility(
        result, support_model_valid=False,
        numerical_valid=solved["converged"], permit_writeback=False)
    return result


def calculate_corotational_reactions(document, constructions, progress=None):
    lookup = {item.id: item for item in constructions}
    incoming = {item.id: [] for item in constructions}
    for construction in constructions:
        for support in construction.supports:
            target = support.item.transfer_target_construction_id
            if target and target in incoming and target != construction.id:
                incoming[target].append(construction.id)
    solved, visiting = {}, set()

    def solve(construction_id):
        if construction_id in solved:
            return solved[construction_id]
        construction = lookup[construction_id]
        if construction_id in visiting:
            result = solve_corotational_beam(
                construction, trace_construction_loads(construction))
            result["issues"].append("cyclic_load_transfer_graph")
            solved[construction_id] = result
            return result
        visiting.add(construction_id)
        loads = trace_construction_loads(construction)
        upstream_failed = []
        for source_id in incoming[construction_id]:
            source = solve(source_id)
            if not source.get("converged"):
                upstream_failed.append(source_id)
                continue
            # The nonlinear model is diagnostic-only until it implements the
            # same tension-only support physics as the linear model.
            if not source.get("load_transfer_eligible", False):
                upstream_failed.append(source_id)
                continue
            for reaction in source["reactions"]:
                if reaction["transfer_target_construction_id"] != construction_id:
                    continue
                station = reaction["transfer_target_station_mm"]
                if station is not None:
                    loads.append({
                        "source_id": "{}:{}".format(
                            source_id, reaction["support_id"]),
                        "source_type": "transferred_nonlinear_high_hook_load",
                        "mass_kg": reaction["preliminary_high_hook_mass_kg"],
                        "station_mm": station,
                        "evidence": "nonlinear_construction_graph",
                    })
        callback = None
        if progress:
            callback = lambda state: progress(construction_id, state)
        result = solve_corotational_beam(
            construction, loads, progress=callback)
        for source_id in upstream_failed:
            result["issues"].append(
                "upstream_nonlinear_load_transfer_ineligible:{}".format(
                    source_id))
        visiting.remove(construction_id)
        solved[construction_id] = result
        if progress:
            progress(construction_id, {"completed": True})
        return result

    for construction in constructions:
        solve(construction.id)
    return {
        "status": "DIAGNOSTIC_DO_NOT_WRITE_TO_VECTORWORKS",
        "limitations": [
            "Two-dimensional corotational open-chain model",
            "Horizontal restraint is applied at the first lift point only",
            "Diagnostic nonlinear results are not propagated as loads",
        ],
        "constructions": [solved[item.id] for item in constructions],
    }
