"""Load-transfer orchestration around independently testable solvers."""

from .beam_statics import solve_two_support_beam, trace_construction_loads
from .continuous_beam import solve_continuous_beam


def _solve_local(construction, loads):
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
    solved, visiting = {}, set()

    def solve(construction_id):
        if construction_id in solved:
            return solved[construction_id]
        if construction_id in visiting:
            result = _solve_local(
                lookup[construction_id],
                trace_construction_loads(lookup[construction_id]))
            result["status"] = "not_calculated"
            result["issues"].append("cyclic_load_transfer_graph")
            solved[construction_id] = result
            return result
        visiting.add(construction_id)
        loads = trace_construction_loads(lookup[construction_id])
        for source_id in incoming[construction_id]:
            source = solve(source_id)
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
            "Three or more supports use a first-order linear 3D frame model",
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
