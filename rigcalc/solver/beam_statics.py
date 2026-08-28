"""Small, directly inspectable beam-statics functions.

This module contains mechanics only. It must not import Vectorworks, scanners,
dialogs, report writers, or object handles.
"""


def trace_construction_loads(construction):
    """Convert attached model objects to auditable station/mass load records."""
    loads = []
    for truss in construction.truss_segments:
        station = construction.station_map.get(truss.id)
        if station and truss.self_weight_kg > 0:
            loads.append({
                "source_id": truss.id, "source_type": "truss_self_weight",
                "mass_kg": truss.self_weight_kg,
                "station_mm": (station.start_station_mm +
                               station.end_station_mm) / 2.0,
                "evidence": "TrussItem.Weight",
            })
    for attached in construction.point_loads:
        item, attachment = attached.item, attached.attachment
        if item.weight_kg is not None and attachment.global_station_mm is not None:
            loads.append({
                "source_id": item.id, "source_type": item.record_type,
                "mass_kg": item.weight_kg,
                "station_mm": attachment.global_station_mm,
                "evidence": attachment.method,
            })
    for attached in construction.distributed_loads:
        item, attachment = attached.item, attached.attachment
        station = attachment.global_station_mm
        if item.total_mass_kg is not None and station is not None:
            end_station = attachment.end_global_station_mm
            if end_station is None:
                end_station = station + (item.length_mm or 0.0)
            interval_start = min(station, end_station)
            interval_end = max(station, end_station)
            loads.append({
                "source_id": item.id, "source_type": item.record_type,
                "mass_kg": item.total_mass_kg,
                "station_mm": (interval_start + interval_end) / 2.0,
                "interval_start_mm": interval_start,
                "interval_end_mm": interval_end,
                "mass_per_m_kg": item.mass_per_m_kg,
                "evidence": attachment.method,
            })
    return loads


def solve_two_support_beam(construction, loads):
    """Solve an open beam using vertical force and moment equilibrium."""
    supports = sorted(
        (item for item in construction.supports
         if item.attachment.global_station_mm is not None),
        key=lambda item: (item.attachment.global_station_mm, item.item.id))
    result = {
        "construction_id": construction.id,
        "construction_name": construction.label,
        "status": "not_calculated",
        "method": None, "loads": loads,
        "writeback_eligible": False,
        "total_applied_mass_kg": sum(item["mass_kg"] for item in loads),
        "reactions": [], "issues": [],
    }
    stations = sorted({
        round(item.attachment.global_station_mm, 6) for item in supports})
    if construction.stationing != "open_chain":
        result["issues"].append("requires_branched_or_loop_solver")
    elif len(supports) != 2 or len(stations) != 2:
        result["issues"].append("requires_exactly_two_distinct_supports")
    elif not loads:
        result["issues"].append("no_applied_loads")
    else:
        left, right = supports
        a, b = (left.attachment.global_station_mm,
                right.attachment.global_station_mm)
        span = b - a
        if span <= 1e-6:
            result["issues"].append("zero_support_span")
        else:
            right_reaction = sum(
                load["mass_kg"] * (load["station_mm"] - a) / span
                for load in loads)
            total = result["total_applied_mass_kg"]
            for support, reaction in (
                    (left, total - right_reaction), (right, right_reaction)):
                result["reactions"].append(_reaction_record(support, reaction))
            result["status"] = "preliminary"
            result["method"] = "two_support_static_equilibrium"
            result["writeback_eligible"] = True
    return result


def _reaction_record(support, reaction_mass_kg):
    item, attachment = support.item, support.attachment
    return {
        "support_id": item.id, "support_name": item.name,
        "support_hoist_id": item.hoist_id,
        "support_kind": item.support_kind,
        "station_mm": attachment.global_station_mm,
        "reaction_mass_kg": reaction_mass_kg,
        "hoist_and_chain_mass_kg": item.weight_with_chain_kg,
        "preliminary_high_hook_mass_kg": (
            reaction_mass_kg + item.weight_with_chain_kg),
        "capacity_kg": item.capacity_kg,
        "transfer_target_construction_id": item.transfer_target_construction_id,
        "transfer_target_station_mm": item.transfer_target_station_mm,
        "is_structural_link": item.is_structural_link,
    }
