from rigcalc.model.construction import Construction

from .attachments import attach_document_objects
from .connections import detect_connections
from .stationing import build_adjacency, build_station_map, connected_components, order_component


def _connection_warning(connection):
    if connection.method != "inferred_collinear":
        return None
    return "{}:{} to {}:{} inferred ({:.1f} mm endpoint discrepancy)".format(
        connection.a, connection.a_port, connection.b, connection.b_port,
        connection.longitudinal_error_mm,
    )


def build_constructions(document):
    connections = detect_connections(document.trusses)
    adjacency = build_adjacency(document.trusses, connections)
    lookup = {truss.id: truss for truss in document.trusses}
    constructions = []
    components = connected_components(adjacency)
    # Geometry and explicit connection evidence determine components. VW
    # system identifiers are applied only afterwards as human-readable IDs.
    components.sort(key=lambda ids: min((lookup[item].position.x, lookup[item].position.y, item) for item in ids))
    for index, component in enumerate(components, 1):
        local_connections = [item for item in connections if item.a in component and item.b in component]
        ordered, stationing = order_component(component, adjacency, lookup, local_connections)
        station_map, span = ({}, None)
        if ordered:
            station_map, span = build_station_map(ordered, lookup, local_connections)
        trusses = [lookup[item] for item in component]
        warnings = [warning for warning in map(_connection_warning, local_connections) if warning]
        system_names = sorted({
            item.vw_truss_system for item in trusses
            if item.vw_truss_system and not item.vw_truss_system.startswith("HP:")
        })
        hp_names = sorted({
            item.vw_truss_system.replace("HP:", "HP-", 1)
            for item in trusses if item.vw_truss_system.startswith("HP:")
        })
        position_names = sorted({
            item.source_position_name for item in trusses
            if item.source_position_name
        })
        hp_truss_systems = sorted({
            item.vw_truss_line.split("-", 1)[0] for item in trusses
            if item.source_position_name and item.vw_truss_line
        })
        if position_names:
            display_name = "+".join(position_names)
            if hp_truss_systems:
                display_name += " [{}]".format("+".join(hp_truss_systems))
        else:
            display_name = "+".join(system_names or hp_names)
        constructions.append(Construction(
            id="__component_{}".format(index),
            truss_segments=trusses,
            connections=local_connections,
            stationing=stationing,
            name=display_name,
            source_system_names=system_names,
            ordered_truss_ids=ordered,
            station_map=station_map,
            nominal_truss_length_mm=sum(item.nominal_length_mm for item in trusses if item.is_line),
            structural_span_mm=span,
            warnings=warnings,
        ))
    # A disconnected VW system can produce several components with the same
    # name. The suffix makes those components unambiguous without pretending
    # the shared system metadata proves a structural connection.
    by_name = {}
    for construction in constructions:
        if construction.name:
            by_name.setdefault(construction.name, []).append(construction)
    for name, matches in by_name.items():
        if len(matches) > 1:
            for part, construction in enumerate(matches, 1):
                construction.name = "{}#{}".format(name, part)
    unnamed = 0
    for construction in constructions:
        if not construction.name:
            unnamed += 1
            construction.name = "UNNAMED-{:02d}".format(unnamed)
        construction.id = construction.name
    attach_document_objects(document, constructions)
    return constructions
