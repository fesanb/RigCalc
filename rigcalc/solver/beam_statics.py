"""Small, directly inspectable beam-statics functions.

This module contains mechanics only. It must not import Vectorworks, scanners,
dialogs, report writers, or object handles.
"""

from .validation import finalize_eligibility
from .inclined_geometry import inclined_station_coordinates, horizontal_coordinate


PLANAR_BEAM_ELEVATION_TOLERANCE_MM = 1.0


def planar_beam_geometry_issue(construction):
    """Return an issue when an open chain is not level in the solver plane."""
    for truss in construction.truss_segments:
        if (truss.is_line and
                abs(truss.end.z-truss.start.z) >
                PLANAR_BEAM_ELEVATION_TOLERANCE_MM):
            return "unsupported_inclined_truss_geometry:{}".format(truss.id)
    return None


def trace_construction_loads(construction):
    """Convert attached model objects to auditable station/mass load records."""
    loads = []
    for truss in construction.truss_segments:
        station = construction.station_map.get(truss.id)
        if station and truss.self_weight_kg > 0:
            interval_start = min(
                station.start_station_mm, station.end_station_mm)
            interval_end = max(
                station.start_station_mm, station.end_station_mm)
            length_m = (interval_end-interval_start) / 1000.0
            loads.append({
                "source_id": truss.id, "source_type": "truss_self_weight",
                "mass_kg": truss.self_weight_kg,
                "station_mm": (interval_start + interval_end) / 2.0,
                "interval_start_mm": interval_start,
                "interval_end_mm": interval_end,
                "mass_per_m_kg": (
                    truss.self_weight_kg / length_m if length_m > 0.0
                    else None),
                "evidence": "TrussItem.Weight (total segment mass)",
            })
        if station and truss.cable_load_kg_m > 0:
            length_m = truss.geometric_length_mm / 1000.0
            loads.append({
                "source_id": "{}:cable".format(truss.id),
                "source_type": "cable_flat_rate",
                "mass_kg": truss.cable_load_kg_m * length_m,
                "station_mm": (station.start_station_mm +
                               station.end_station_mm) / 2.0,
                "interval_start_mm": min(
                    station.start_station_mm, station.end_station_mm),
                "interval_end_mm": max(
                    station.start_station_mm, station.end_station_mm),
                "mass_per_m_kg": truss.cable_load_kg_m,
                "evidence": "RigCalc calculation scope setting",
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
        "load_transfer_eligible": False,
        "total_applied_mass_kg": sum(item["mass_kg"] for item in loads),
        "reactions": [], "issues": [],
    }
    geometry_issue = planar_beam_geometry_issue(construction)
    if geometry_issue:
        result["issues"].append(geometry_issue)
        return result
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
            reaction_total = sum(
                item["reaction_mass_kg"] for item in result["reactions"])
            reaction_moment = sum(
                item["reaction_mass_kg"]*item["station_mm"]/1000.0
                for item in result["reactions"])
            applied_moment = sum(
                item["mass_kg"]*item["station_mm"]/1000.0
                for item in loads)
            vertical_error = reaction_total-result["total_applied_mass_kg"]
            moment_error = reaction_moment-applied_moment
            vertical_tolerance = max(
                0.01, abs(result["total_applied_mass_kg"])*1.0e-6)
            moment_tolerance = max(0.01, abs(applied_moment)*1.0e-6)
            result["validation"] = {
                "vertical_equilibrium_error_kg": vertical_error,
                "vertical_equilibrium_tolerance_kg": vertical_tolerance,
                "vertical_equilibrium_ok": (
                    abs(vertical_error) <= vertical_tolerance),
                "moment_equilibrium_error_kg_m": moment_error,
                "moment_equilibrium_tolerance_kg_m": moment_tolerance,
                "moment_equilibrium_ok": abs(moment_error) <= moment_tolerance,
            }
            # Preserve signed reactions as uplift diagnostics, but never use a
            # bilateral solution with hoist uplift as an approved load source.
            support_model_valid = not any(
                item["reaction_mass_kg"] < -1.0e-6 and
                not item["is_structural_link"]
                for item in result["reactions"])
            finalize_eligibility(
                result, support_model_valid=support_model_valid)
    return result


def solve_inclined_two_support_beam(construction, loads):
    """Diagnostic global-equilibrium result for a planar inclined two-support chain."""
    supports = sorted((item for item in construction.supports
                       if item.attachment.global_station_mm is not None),
                      key=lambda item: item.attachment.global_station_mm)
    output = {"construction_id": construction.id, "construction_name": construction.label,
              "status": "not_calculated", "method": "inclined_planar_global_equilibrium_diagnostic",
              "loads": loads, "writeback_eligible": False, "load_transfer_eligible": False,
              "total_applied_mass_kg": sum(item["mass_kg"] for item in loads),
              "reactions": [], "issues": []}
    coordinates, issue = inclined_station_coordinates(construction)
    if issue:
        output["issues"].append(issue)
    elif len(supports) != 2 or not loads:
        output["issues"].append("requires_exactly_two_distinct_supports")
    else:
        left, right = supports
        a = horizontal_coordinate(left.attachment.global_station_mm, coordinates)
        b = horizontal_coordinate(right.attachment.global_station_mm, coordinates)
        if a is None or b is None or abs(b-a) <= 1.0e-6:
            output["issues"].append("invalid_inclined_support_geometry")
        else:
            right_mass = sum(item["mass_kg"] *
                             (horizontal_coordinate(item["station_mm"], coordinates)-a)/(b-a)
                             for item in loads)
            total = output["total_applied_mass_kg"]
            output["reactions"] = [_reaction_record(left, total-right_mass),
                                   _reaction_record(right, right_mass)]
            output["status"] = "diagnostic"
            output["issues"].append("inclined_geometry_diagnostic_not_writeback_source")
    return output


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
