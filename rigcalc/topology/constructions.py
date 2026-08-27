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
    # Stable construction IDs follow geometric position, not scan order.
    components.sort(key=lambda ids: min((lookup[item].position.x, lookup[item].position.y, item) for item in ids))
    for index, component in enumerate(components, 1):
        local_connections = [item for item in connections if item.a in component and item.b in component]
        ordered, stationing = order_component(component, adjacency, lookup, local_connections)
        station_map, span = ({}, None)
        if ordered:
            station_map, span = build_station_map(ordered, lookup, local_connections)
        trusses = [lookup[item] for item in component]
        warnings = [warning for warning in map(_connection_warning, local_connections) if warning]
        constructions.append(Construction(
            id="C{:02d}".format(index),
            truss_segments=trusses,
            connections=local_connections,
            stationing=stationing,
            ordered_truss_ids=ordered,
            station_map=station_map,
            nominal_truss_length_mm=sum(item.nominal_length_mm for item in trusses if item.is_line),
            structural_span_mm=span,
            warnings=warnings,
        ))
    attach_document_objects(document, constructions)
    return constructions
