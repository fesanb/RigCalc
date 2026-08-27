def mm_to_m(value):
    return "-" if value is None else "{:.3f} m".format(value / 1000.0)


def _item_name(item):
    return getattr(item, "hoist_id", "") or item.name or item.id


def make_text_report(document, constructions):
    lines = ["RIGCALC GEOMETRY MODEL", "=" * 72,
             "Constructions: {}".format(len(constructions)),
             "Truss objects: {}".format(len(document.trusses)),
             "Hoists: {}".format(len(document.supports)),
             "Loads: {}".format(len(document.point_loads)), ""]
    for construction in constructions:
        lines.extend([
            "=" * 72, construction.id, "=" * 72,
            "Nominal truss length: {}".format(mm_to_m(construction.nominal_truss_length_mm)),
            "Structural span: {}".format(mm_to_m(construction.structural_span_mm)),
            "Stationing: {}".format(construction.stationing), "", "TRUSS",
        ])
        lookup = {item.id: item for item in construction.truss_segments}
        order = construction.ordered_truss_ids or sorted(lookup)
        for truss_id in order:
            truss = lookup[truss_id]
            station = construction.station_map.get(truss_id)
            station_text = ""
            if station:
                station_text = " station {} -> {} ({})".format(
                    mm_to_m(station.start_station_mm), mm_to_m(station.end_station_mm), station.direction)
            lines.append("  {} {} [{}] L={}{}".format(
                truss.id, truss.name, truss.item_type, mm_to_m(truss.nominal_length_mm), station_text))
        lines.extend(["", "CONNECTIONS"])
        if not construction.connections:
            lines.append("  none")
        for connection in construction.connections:
            lines.append("  {}:{} <-> {}:{} {} {} ({:.1f} mm)".format(
                connection.a, connection.a_port, connection.b, connection.b_port,
                connection.confidence, connection.method, connection.distance_mm))
        if construction.warnings:
            lines.extend(["", "WARNINGS"] + ["  " + warning for warning in construction.warnings])
        lines.extend(["", "CALCULATION INPUT", "  Structural span: {}".format(mm_to_m(construction.structural_span_mm)), "", "  SUPPORTS"])
        supports = sorted(construction.supports, key=lambda item: item.attachment.global_station_mm if item.attachment.global_station_mm is not None else float("inf"))
        lines.extend(["    none"] if not supports else [
            "    {}  {}  axis offset {:.1f} mm{}".format(mm_to_m(value.attachment.global_station_mm), _item_name(value.item), value.attachment.distance_from_truss_axis_mm, " WARNING" if value.attachment.warning else "")
            for value in supports])
        lines.extend(["", "  POINT LOADS"])
        loads = sorted(construction.point_loads, key=lambda item: item.attachment.global_station_mm if item.attachment.global_station_mm is not None else float("inf"))
        lines.extend(["    none"] if not loads else [
            "    {}  {}  {}  axis offset {:.1f} mm{}".format(
                mm_to_m(value.attachment.global_station_mm), _item_name(value.item),
                "{:.2f} kg".format(value.item.weight_kg) if value.item.weight_kg is not None else str(value.item.weight_raw),
                value.attachment.distance_from_truss_axis_mm, " WARNING" if value.attachment.warning else "")
            for value in loads])
        lines.append("")
    return "\n".join(lines)
