def mm_to_m(value):
    return "-" if value is None else "{:.3f} m".format(value / 1000.0)


def _item_name(item):
    return getattr(item, "hoist_id", "") or item.name or item.id


def make_text_report(document, constructions):
    lines = ["RIGCALC GEOMETRY MODEL", "=" * 72,
             "Constructions: {}".format(len(constructions)),
             "Truss objects: {}".format(len(document.trusses)),
             "Hoists: {}".format(len(document.supports)),
             "Loads: {}".format(len(document.point_loads)),
             "Unassigned hoists: {}".format(len(document.unassigned_supports)),
             "Unassigned loads: {}".format(len(document.unassigned_point_loads)), ""]
    for construction in constructions:
        lines.extend([
            "=" * 72,
            "{} ({})".format(construction.label, construction.id)
            if construction.label != construction.id else construction.id,
            "=" * 72,
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
            section = truss.mechanical_section
            if section:
                lines.append(
                    "    SECTION {} | E {:.3f} GPa | G {:.3f} GPa | "
                    "A {:.3f} cm2 | Iyy {:.3f} cm4 | Izz {:.3f} cm4".format(
                        section.identifier,
                        (section.elastic_modulus_pa or 0.0) / 1.0e9,
                        (section.shear_modulus_pa or 0.0) / 1.0e9,
                        (section.area_m2 or 0.0) / 1.0e-4,
                        (section.iyy_m4 or 0.0) / 1.0e-8,
                        (section.izz_m4 or 0.0) / 1.0e-8))
            elif truss.cross_section_id:
                lines.append("    SECTION {} | UNRESOLVED".format(
                    truss.cross_section_id))
            for issue in truss.cross_section_issues:
                lines.append("    SECTION ISSUE: " + issue)
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
            "    {}  {}  axis offset {:.1f} mm clearance {:.1f} mm {} {}".format(
                mm_to_m(value.attachment.global_station_mm), _item_name(value.item),
                value.attachment.distance_from_truss_axis_mm,
                value.attachment.carrier_clearance_mm or 0.0,
                value.attachment.method,
                "WARNING" if value.attachment.warning else "")
            for value in supports])
        lines.extend(["", "  POINT LOADS"])
        loads = sorted(construction.point_loads, key=lambda item: item.attachment.global_station_mm if item.attachment.global_station_mm is not None else float("inf"))
        lines.extend(["    none"] if not loads else [
            "    {}  {}  {}  axis offset {:.1f} mm clearance {:.1f} mm {} {}".format(
                mm_to_m(value.attachment.global_station_mm), _item_name(value.item),
                "{:.2f} kg".format(value.item.weight_kg) if value.item.weight_kg is not None else str(value.item.weight_raw),
                value.attachment.distance_from_truss_axis_mm,
                value.attachment.carrier_clearance_mm or 0.0,
                value.attachment.method,
                "WARNING" if value.attachment.warning else "")
            for value in loads])
        lines.extend(["", "  DISTRIBUTED LOADS"])
        distributed = sorted(
            construction.distributed_loads,
            key=lambda item: item.attachment.global_station_mm
            if item.attachment.global_station_mm is not None else float("inf"))
        lines.extend(["    none"] if not distributed else [
            "    {}  {}  total {:.2f} kg over {:.3f} m ({:.2f} kg/m) {}".format(
                mm_to_m(value.attachment.global_station_mm), _item_name(value.item),
                value.item.total_mass_kg or 0.0,
                (value.item.length_mm or 0.0) / 1000.0,
                value.item.mass_per_m_kg or 0.0,
                value.attachment.method)
            for value in distributed])
        lines.append("")
    if document.unassigned_supports or document.unassigned_point_loads:
        lines.extend(["=" * 72, "UNASSIGNED OBJECTS", "=" * 72])
        for item in document.unassigned_supports:
            lines.append("  HOIST {} {} at ({:.1f}, {:.1f}, {:.1f})".format(
                item.id, _item_name(item), item.position.x, item.position.y,
                item.position.z))
            diagnostic = document.unassigned_support_diagnostics.get(item.id, {})
            if diagnostic:
                lines.append("    REASON: {}".format(diagnostic.get("reason")))
                for label in ("nearest_3d", "nearest_plan"):
                    nearest = diagnostic.get(label)
                    if nearest:
                        lines.append(
                            "    {}: {} / {} clearance {:.1f} mm".format(
                                label, nearest["construction_id"],
                                nearest["truss_id"],
                                nearest["carrier_clearance_mm"]))
        for item in document.unassigned_point_loads:
            lines.append("  LOAD {} {} at ({:.1f}, {:.1f}, {:.1f})".format(
                item.id, _item_name(item), item.position.x, item.position.y,
                item.position.z))
        lines.append("")
    return "\n".join(lines)
