"""Diagnostic corotational adapter for a straight inclined planar chain.

The adapter deliberately remains diagnostic-only: it explores fixed support
contact states but does not yet apply hoist/chain contact mass or model cable
slack/re-engagement as deformable unilateral elements.
"""

from itertools import combinations
from math import sqrt

from .beam_statics import _reaction_record
from .continuous_beam import (GRAVITY_M_S2, MAX_EXHAUSTIVE_TENSION_ONLY_HOISTS,
                              STATION_TOLERANCE_MM, _section_at,
                              _section_result, _unique_stations)
from .corotational import (CorotationalElement, CorotationalModel,
                           CorotationalCable, CorotationalNode,
                           solve_corotational)
from .contact import contact_mass_by_support, engaged_contact_mass_loads
from .deflection import build_deflection_summary, support_span_midpoints
from .inclined_geometry import inclined_station_coordinates, planar_coordinate


def _stations(coordinates, all_supports, active_supports, loads):
    values = (set(coordinates) |
              {item.attachment.global_station_mm for item in all_supports} |
              set(support_span_midpoints(
                  [item.attachment.global_station_mm for item in active_supports])) |
              {item["station_mm"] for item in loads})
    for load in loads:
        if "interval_start_mm" in load:
            values.add(load["interval_start_mm"])
            values.add(load["interval_end_mm"])
    return sorted(values)


def _node_loads(stations, nodes, loads):
    loads_by_station = [[0.0, 0.0, 0.0] for _ in stations]
    for index, station in enumerate(stations):
        loads_by_station[index][1] -= sum(
            item["mass_kg"]*GRAVITY_M_S2 for item in loads
            if "interval_start_mm" not in item and
            abs(item["station_mm"]-station) <= STATION_TOLERANCE_MM)
    for index, (start, end) in enumerate(zip(stations, stations[1:])):
        length = sqrt((nodes[index+1][0]-nodes[index][0])**2 +
                      (nodes[index+1][1]-nodes[index][1])**2)
        if length <= 0.0:
            continue
        mass = 0.0
        for item in loads:
            if "interval_start_mm" not in item:
                continue
            if (start >= item["interval_start_mm"]-STATION_TOLERANCE_MM and
                    end <= item["interval_end_mm"]+STATION_TOLERANCE_MM):
                total_length = 0.0
                for inner, (first, last) in enumerate(zip(stations, stations[1:])):
                    if (first >= item["interval_start_mm"]-STATION_TOLERANCE_MM and
                            last <= item["interval_end_mm"]+STATION_TOLERANCE_MM):
                        total_length += sqrt(
                            (nodes[inner+1][0]-nodes[inner][0])**2 +
                            (nodes[inner+1][1]-nodes[inner][1])**2)
                if total_length > 0.0:
                    mass += item["mass_kg"]*length/total_length
        if mass <= 0.0:
            continue
        # Fixed global vertical gravity resolved into the element's transverse
        # direction.  Axial gravity has no fixed-end moment; the transverse
        # part has the standard Euler-Bernoulli end moments.
        horizontal = (nodes[index+1][0]-nodes[index][0])/length
        force_n = mass*GRAVITY_M_S2
        loads_by_station[index][1] -= force_n/2.0
        loads_by_station[index+1][1] -= force_n/2.0
        q_transverse = -force_n/length*horizontal
        loads_by_station[index][2] += -q_transverse*length**2/12.0
        loads_by_station[index+1][2] += q_transverse*length**2/12.0
    return loads_by_station


def solve_inclined_corotational_beam(construction, loads, _active_ids=None,
                                     _signed_reactions=None):
    all_supports = sorted(
        (item for item in construction.supports
         if item.attachment.global_station_mm is not None),
        key=lambda item: item.attachment.global_station_mm)
    supports = [item for item in all_supports
                if _active_ids is None or item.item.id in _active_ids]
    result = {
        "construction_id": construction.id,
        "construction_name": construction.label,
        "status": "not_calculated",
        "method": "inclined_planar_corotational_diagnostic",
        "loads": loads,
        "load_model": {
            "direction": "fixed_global_negative_z",
            "reference_configuration": "undeformed_inclined_chord_geometry",
            "distributed_load": "equivalent_nodal_gravity_load_not_follower",
            "contact_mass": "engaged hoist/chain mass is a point load",
        },
        "writeback_eligible": False,
        "load_transfer_eligible": False,
        "total_applied_mass_kg": sum(item["mass_kg"] for item in loads),
        "reactions": [], "stations": [], "element_forces": [], "issues": [],
    }
    coordinates, issue = inclined_station_coordinates(construction)
    if issue:
        result["issues"].append(issue)
        return result
    if len(supports) < 2 or not loads:
        result["issues"].append("requires_two_or_more_distinct_supports")
        return result
    # Vectorworks geometry commonly contains mathematically equal station
    # values with tiny floating-point differences.  They must not create a
    # zero-length frame element.
    stations = _unique_stations(
        _stations(coordinates, all_supports, supports, loads))
    points = [planar_coordinate(station, coordinates) for station in stations]
    if any(x is None or z is None for x, z in points):
        result["issues"].append("unsupported_partial_inclined_station")
        return result
    cable_supports = [item for item in supports
                      if (not item.item.is_structural_link and
                          item.item.object_position is not None and
                          item.item.object_position.z >
                          item.item.position.z+1.0)]
    # A cable model is only enabled when every motor in this construction has
    # an observed upper point.  We never invent an anchor from a trim field.
    use_cables = (bool(cable_supports) and
                  len(cable_supports) == len([item for item in supports
                                              if not item.item.is_structural_link]) and
                  _active_ids is None)
    if use_cables:
        # The cable supports are engaged from the start of this nonlinear
        # solve, so their documented hoist/chain mass belongs at the lower
        # contact point just as it does for the level-chain contact model.
        loads = list(loads) + engaged_contact_mass_loads(cable_supports)
        result["loads"] = loads
        result["total_applied_mass_kg"] = sum(
            item["mass_kg"] for item in loads)
    active_stations = {round(item.attachment.global_station_mm, 6)
                       for item in supports}
    anchor = min(active_stations)
    node_loads = _node_loads(stations, points, loads)
    nodes = [CorotationalNode(
        "N{:04d}".format(index), x/1000.0, z/1000.0,
        restrained=(round(station, 6) == anchor,
                    False if use_cables else round(station, 6) in active_stations,
                    False),
        load=tuple(node_loads[index]))
        for index, (station, (x, z)) in enumerate(zip(stations, points))]
    elements = []
    element_sections = {}
    for index, (start, end) in enumerate(zip(stations, stations[1:])):
        section = _section_at(construction, (start+end)/2.0)
        if section is None:
            result["issues"].append(
                "mechanical_section_missing_at_{:.3f}_mm".format((start+end)/2.0))
            return result
        required = (section.elastic_modulus_pa, section.area_m2, section.iyy_m4)
        if any(value is None or value <= 0.0 for value in required):
            result["issues"].append(
                "mechanical_section_incomplete:{}".format(section.identifier))
            return result
        elements.append(CorotationalElement(
            "E{:04d}".format(index), nodes[index].id, nodes[index+1].id,
            section.elastic_modulus_pa, section.area_m2, section.iyy_m4))
        element_sections["E{:04d}".format(index)] = _section_result(section)
    cables = []
    if use_cables:
        node_by_station = {round(station, 6): node
                           for station, node in zip(stations, nodes)}
        for support in cable_supports:
            lower = node_by_station[round(
                support.attachment.global_station_mm, 6)]
            upper = support.item.object_position
            # ``lower.x`` is the local in-plane coordinate along the truss
            # chain.  A Vectorworks world X value is not interchangeable
            # with it (many rigs run along world Y).  The scanned motor and
            # lower pickup share plan position for a vertical chain, so the
            # physical cable anchor is directly above this projected station.
            anchor_node = CorotationalNode(
                "CABLE_TOP:{}".format(support.item.id),
                lower.x, upper.z/1000.0,
                restrained=(True, True, True))
            nodes.append(anchor_node)
            length = sqrt((anchor_node.x-lower.x)**2 +
                          (anchor_node.z-lower.z)**2)
            cables.append(CorotationalCable(
                support.item.id, anchor_node.id, lower.id,
                # A finite axial stiffness gives Newton iteration a usable
                # tangent through the slack/taut transition.  It is stiff
                # relative to the frame while avoiding an artificial rigid
                # constraint at the first load increment.
                1.0e7, length))
    try:
        solved = solve_corotational(
            CorotationalModel(nodes, elements, cables=cables),
            # Multi-hoist inclined frames enter the cable-contact branch from
            # an unloaded, zero-tension state.  Smaller initial increments
            # give Newton iteration a stable path onto that branch.
            initial_load_step=0.02, minimum_load_step=0.00025,
            maximum_load_step=0.15, max_iterations=70)
    except ValueError as error:
        result["issues"].append(str(error))
        return result
    result.update({
        "converged": solved["converged"],
        "iterations": solved["iterations"],
        "completed_load_factor": solved["completed_load_factor"],
        "load_history": solved["load_history"],
    })
    cable_by_id = {item["cable_id"]: item
                   for item in solved.get("cable_results", [])}
    for support in supports:
        index = next(index for index, station in enumerate(stations)
                     if abs(station-support.attachment.global_station_mm)
                     <= STATION_TOLERANCE_MM)
        if support.item.id in cable_by_id:
            cable = cable_by_id[support.item.id]
            reaction = _reaction_record(
                support, cable["tension_n"]/GRAVITY_M_S2)
            reaction["support_active"] = bool(cable["tension_n"] > 1.0e-5)
            reaction["vertical_reaction_mass_kg"] = (
                cable["tension_n"] * abs(
                    (nodes[index].z - next(node.z for node in nodes
                     if node.id == cable["node_i"])) / cable["length_m"]
                ) / GRAVITY_M_S2)
            reaction["support_force_model"] = "tension_only_cable"
            result["reactions"].append(reaction)
        else:
            result["reactions"].append(_reaction_record(
                support, solved["node_reactions"][nodes[index].id][1]/GRAVITY_M_S2))
    contact_masses = contact_mass_by_support(loads)
    for reaction in result["reactions"]:
        mass = contact_masses.get(reaction["support_id"], 0.0)
        if mass:
            reaction["contact_mass_included_kg"] = mass
            # The reaction already includes this contact load. It must never
            # be added again as an apparently approved High Hook value.
            reaction["preliminary_high_hook_mass_kg"] = (
                reaction["reaction_mass_kg"])
            reaction["high_hook_mass_basis"] = (
                "reaction_includes_engaged_contact_mass_diagnostic")
    if _signed_reactions is None:
        _signed_reactions = [dict(item) for item in result["reactions"]]
    if _active_ids is None and not use_cables:
        hoists = [item for item in all_supports if not item.item.is_structural_link]
        if len(hoists) <= MAX_EXHAUSTIVE_TENSION_ONLY_HOISTS:
            candidates = []
            for count in range(len(hoists)+1):
                for selected in combinations(hoists, count):
                    active_ids = ({item.item.id for item in selected} |
                                  {item.item.id for item in all_supports
                                   if item.item.is_structural_link})
                    if len(active_ids) < 2:
                        continue
                    candidate_loads = list(loads) + engaged_contact_mass_loads(
                        selected)
                    candidate = solve_inclined_corotational_beam(
                        construction, candidate_loads, active_ids,
                        _signed_reactions)
                    if (candidate["status"] != "diagnostic" or
                            not candidate.get("converged") or
                            any(item["reaction_mass_kg"] < -1.0e-6
                                for item in candidate["reactions"])):
                        continue
                    displacement = {round(item["station_mm"], 6):
                                    item["displacements"]["uz_m"]
                                    for item in candidate["stations"]}
                    if any(displacement.get(round(item.attachment.global_station_mm, 6),
                                            float("inf")) > 1.0e-8
                           for item in hoists if item.item.id not in active_ids):
                        continue
                    candidates.append(candidate)
            if candidates:
                result = max(candidates, key=lambda item: len(item["reactions"]))
                active = {item["support_id"]: item for item in result["reactions"]}
                signed = {item["support_id"]: item for item in _signed_reactions}
                result["reactions"] = []
                for support in all_supports:
                    reaction = active.get(support.item.id,
                                          _reaction_record(support, 0.0))
                    reaction["support_active"] = support.item.id in active
                    reaction["unconstrained_reaction_mass_kg"] = (
                        signed.get(support.item.id, {}).get("reaction_mass_kg"))
                    result["reactions"].append(reaction)
                result["active_set_validation"] = {
                    "method": "exhaustive_inclined_corotational_contact_state",
                    "candidate_sets_valid": len(candidates),
                    "contact_mass_model": "engaged_support_point_load",
                }
                return result
            result["issues"].append("tension_only_active_set_no_feasible_solution")
        else:
            result["issues"].append("tension_only_active_set_limit_exceeded")
    result["stations"] = [{
        "node_id": node.id, "station_mm": station,
        "displacements": dict(zip(
            ("ux_m", "uy_m", "uz_m", "rx_rad", "ry_rad", "rz_rad"),
            (solved["node_displacements"][node.id][0], 0.0,
             solved["node_displacements"][node.id][1], 0.0,
             solved["node_displacements"][node.id][2], 0.0))),
    } for node, station in zip(nodes, stations)]
    reaction_total = sum(item.get("vertical_reaction_mass_kg",
                                  item["reaction_mass_kg"])
                         for item in result["reactions"])
    applied_moment = sum(item["mass_kg"]*planar_coordinate(
        item["station_mm"], coordinates)[0]/1000.0 for item in loads)
    reaction_moment = sum(item.get("vertical_reaction_mass_kg",
                                   item["reaction_mass_kg"])*planar_coordinate(
        item["station_mm"], coordinates)[0]/1000.0
                          for item in result["reactions"])
    result["validation"] = {
        "vertical_equilibrium_error_kg": reaction_total-result["total_applied_mass_kg"],
        "vertical_equilibrium_ok": abs(
            reaction_total-result["total_applied_mass_kg"]) <= 0.01,
        "moment_equilibrium_error_kg_m": reaction_moment-applied_moment,
        "moment_equilibrium_ok": abs(reaction_moment-applied_moment) <= 0.01,
        "support_model_valid": False,
        "numerically_valid": bool(solved["converged"]),
        "load_model_valid": True,
    }
    result["deflection"] = build_deflection_summary(
        result["stations"],
        [item.attachment.global_station_mm for item in supports])
    result["element_forces"] = [{
        "element_id": item["element_id"],
        "start_station_mm": stations[int(item["element_id"][1:])],
        "end_station_mm": stations[int(item["element_id"][1:])+1],
        "length_m": item["length_m"],
        "cross_section": element_sections[item["element_id"]],
        "i": item["i"], "j": item["j"],
    } for item in solved["element_results"]]
    result["status"] = "diagnostic" if solved["converged"] else "not_calculated"
    if not solved["converged"]:
        result["issues"].append("nonlinear_solution_did_not_converge")
    result["issues"].append("diagnostic_not_writeback_source")
    if contact_masses:
        result["issues"].append(
            "tension_only_contact_model_diagnostic_not_writeback_source")
    else:
        result["issues"].append("tension_only_contact_mass_model_not_implemented")
    return result
