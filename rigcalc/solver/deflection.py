"""Helpers for reporting vertical deflection between active supports."""


STATION_TOLERANCE_MM = 1.0e-6


def support_span_midpoints(support_stations):
    stations = sorted(support_stations)
    return [(start + end) / 2.0
            for start, end in zip(stations, stations[1:])]


def _station_at(stations, target_mm):
    return next((item for item in stations
                 if abs(item["station_mm"] - target_mm) <=
                 STATION_TOLERANCE_MM), None)


def _deflection_record(station):
    if station is None:
        return None
    return {
        "station_mm": station["station_mm"],
        "deflection_mm": station["displacements"]["uz_m"] * 1000.0,
    }


def build_deflection_summary(stations, support_stations):
    """Summarize exact solver nodes at midspan and the sampled maximum."""
    if not stations:
        return {"maximum": None, "spans": []}
    maximum_station = max(
        stations, key=lambda item: abs(item["displacements"]["uz_m"]))
    spans = []
    ordered_supports = sorted(support_stations)
    for start, end in zip(ordered_supports, ordered_supports[1:]):
        midpoint = (start + end) / 2.0
        midspan = _deflection_record(_station_at(stations, midpoint))
        candidates = [item for item in stations
                      if start-STATION_TOLERANCE_MM <= item["station_mm"] <=
                      end+STATION_TOLERANCE_MM]
        maximum = _deflection_record(max(
            candidates,
            key=lambda item: abs(item["displacements"]["uz_m"])))
        midspan_abs_mm = abs(midspan["deflection_mm"])
        spans.append({
            "span_start_mm": start,
            "span_end_mm": end,
            "span_length_mm": end-start,
            "midspan": midspan,
            "maximum": maximum,
            "midspan_deflection_ratio": (
                (end-start)/midspan_abs_mm if midspan_abs_mm > 1.0e-12
                else None),
        })
    return {
        "maximum": _deflection_record(maximum_station),
        "spans": spans,
    }
