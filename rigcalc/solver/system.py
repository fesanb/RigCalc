"""Load-transfer orchestration around independently testable solvers."""

from .beam_statics import (solve_inclined_two_support_beam, solve_two_support_beam,
                           planar_beam_geometry_issue, trace_construction_loads)
from .continuous_beam import solve_continuous_beam
from .inclined_beam import solve_inclined_planar_frame
from .validation import load_transfer_eligible


def _solve_local(construction, loads):
    if planar_beam_geometry_issue(construction):
        return solve_inclined_planar_frame(construction, loads)
    distinct = {round(item.attachment.global_station_mm, 6)
                for item in construction.supports
                if item.attachment.global_station_mm is not None}
    if len(distinct) > 2:
        return solve_continuous_beam(construction, loads)
    return solve_two_support_beam(construction, loads)


def calculate_reactions(document, constructions, progress=None):
    lookup = {item.id: item for item in constructions}
    incoming = {item.id: [] for item in constructions}
    for construction in constructions:
        for support in construction.supports:
            target = support.item.transfer_target_construction_id
            if target and target in incoming and target != construction.id:
                incoming[target].append(construction.id)
    outgoing = {
        item.id: set() for item in constructions}
    for target_id, source_ids in incoming.items():
        for source_id in source_ids:
            outgoing[source_id].add(target_id)
    cyclic_ids, path, visited = set(), [], set()

    def find_cycles(construction_id):
        if construction_id in path:
            cyclic_ids.update(path[path.index(construction_id):])
            return
        if construction_id in visited:
            return
        visited.add(construction_id)
        path.append(construction_id)
        for target_id in outgoing[construction_id]:
            find_cycles(target_id)
        path.pop()

    for construction in constructions:
        find_cycles(construction.id)
    solved, visiting = {}, set()

    def solve(construction_id):
        if construction_id in solved:
            return solved[construction_id]
        if construction_id in visiting:
            result = _solve_local(
                lookup[construction_id],
                trace_construction_loads(lookup[construction_id]))
            result["status"] = "not_calculated"
            result["writeback_eligible"] = False
            result["load_transfer_eligible"] = False
            result["issues"].append("cyclic_load_transfer_graph")
            solved[construction_id] = result
            return result
        visiting.add(construction_id)
        loads = trace_construction_loads(lookup[construction_id])
        upstream_issues = []
        for source_id in incoming[construction_id]:
            if source_id in cyclic_ids:
                upstream_issues.append(
                    "upstream_load_transfer_ineligible:{}".format(source_id))
                continue
            source = solve(source_id)
            if not load_transfer_eligible(source):
                loads_rejected = source.get("construction_id", source_id)
                # Do not let a result with failed validation contaminate a
                # downstream calculation.  Keep the downstream result useful,
                # but make the omitted source explicit to the user.
                result_issue = "upstream_load_transfer_ineligible:{}".format(
                    loads_rejected)
                # The result is not created until after its complete load set
                # has been assembled, so retain the issue locally for now.
                upstream_issues.append(result_issue)
                continue
            for reaction in source["reactions"]:
                if reaction["transfer_target_construction_id"] != construction_id:
                    continue
                station = reaction["transfer_target_station_mm"]
                if station is not None:
                    loads.append({
                        "source_id": "{}:{}".format(
                            source_id, reaction["support_id"]),
                        "source_type": "transferred_high_hook_load",
                        "mass_kg": reaction["preliminary_high_hook_mass_kg"],
                        "station_mm": station,
                        "evidence": "construction_graph",
                    })
        result = _solve_local(lookup[construction_id], loads)
        result["issues"].extend(upstream_issues)
        if construction_id in cyclic_ids:
            result["status"] = "not_calculated"
            result["issues"].append("cyclic_load_transfer_graph")
            result["writeback_eligible"] = False
            result["load_transfer_eligible"] = False
        if upstream_issues:
            result["writeback_eligible"] = False
            result["load_transfer_eligible"] = False
        visiting.remove(construction_id)
        solved[construction_id] = result
        return result

    for construction in constructions:
        solve(construction.id)
        if progress:
            progress(construction.id, len(solved), len(constructions))
    return {
        "status": "PRELIMINARY_DO_NOT_WRITE_TO_VECTORWORKS",
        "limitations": [
            "Distributed load interval uses its normalized start, end, and orientation",
            "Open chains with any number of distinct vertical supports are solved",
            "Three or more supports use a first-order planar vertical continuous-beam model",
            "Load transfer requires an acyclic hoist/truss-cross graph",
        ],
        "unassigned": {
            "supports": [item.id for item in document.unassigned_supports],
            "point_loads": [item.id for item in document.unassigned_point_loads],
            "distributed_loads": [
                item.id for item in document.unassigned_distributed_loads],
        },
        "constructions": [solved[item.id] for item in constructions],
    }
