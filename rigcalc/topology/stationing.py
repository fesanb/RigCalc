from rigcalc.model.construction import StationRange


def build_adjacency(trusses, connections):
    adjacency = {truss.id: [] for truss in trusses}
    for connection in connections:
        adjacency[connection.a].append(connection.b)
        adjacency[connection.b].append(connection.a)
    return adjacency


def connected_components(adjacency):
    seen, components = set(), []
    for node in sorted(adjacency):
        if node in seen:
            continue
        stack, component = [node], []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(n for n in adjacency[current] if n not in seen)
        components.append(component)
    return components


def _connection_for(connections, a_id, b_id):
    for connection in connections:
        if connection.a == a_id and connection.b == b_id:
            return connection, connection.a_port
        if connection.b == a_id and connection.a == b_id:
            return connection, connection.b_port
    return None, None


def _physical_endpoint(truss, port):
    if not truss.is_line:
        return truss.position
    return truss.start if port == "start" else truss.end


def order_component(component, adjacency, lookup, connections):
    if max(len(adjacency[node]) for node in component) > 2:
        return [], "branched"
    endpoints = [node for node in component if len(adjacency[node]) <= 1]
    if endpoints:
        # Select the actual free geometric endpoint, not object creation/direction.
        choices = []
        for node in endpoints:
            truss = lookup[node]
            if adjacency[node]:
                neighbour = adjacency[node][0]
                _, connected_port = _connection_for(connections, node, neighbour)
                free_port = "end" if connected_port == "start" else "start"
                point = _physical_endpoint(truss, free_port)
            elif truss.is_line:
                point = min((truss.start, truss.end), key=lambda value: (value.x, value.y))
            else:
                point = truss.position
            choices.append((node, point))
        xs = [point.x for _, point in choices]
        ys = [point.y for _, point in choices]
        primarily_horizontal = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        key = (lambda item: (item[1].x, item[1].y, item[0])) if primarily_horizontal else (lambda item: (item[1].y, item[1].x, item[0]))
        current = min(choices, key=key)[0]
        stationing = "open_chain"
    else:
        current = min(component, key=lambda node: (lookup[node].position.x, lookup[node].position.y, node))
        stationing = "closed_loop_arbitrary_origin"

    ordered, previous = [], None
    while current not in ordered:
        ordered.append(current)
        candidates = sorted(n for n in adjacency[current] if n != previous and n not in ordered)
        if not candidates:
            break
        previous, current = current, candidates[0]
    return ordered, stationing


def build_station_map(ordered, lookup, connections):
    if ordered and all(lookup[item].is_line for item in ordered):
        first = lookup[ordered[0]]
        last = lookup[ordered[-1]]
        if len(ordered) == 1:
            points = (first.start, first.end)
            x_extent = abs(first.end.x - first.start.x)
            y_extent = abs(first.end.y - first.start.y)
            key = (lambda p: (p.x, p.y)) if x_extent >= y_extent else (lambda p: (p.y, p.x))
            origin, terminal = min(points, key=key), max(points, key=key)
        else:
            _, first_port = _connection_for(connections, first.id, ordered[1])
            _, last_port = _connection_for(connections, last.id, ordered[-2])
            origin = first.end if first_port == "start" else first.start
            terminal = last.end if last_port == "start" else last.start
        dx, dy = terminal.x - origin.x, terminal.y - origin.y
        span = (dx * dx + dy * dy) ** 0.5
        if span > 1e-6:
            ux, uy = dx / span, dy / span
            station_map = {}
            for truss_id in ordered:
                truss = lookup[truss_id]
                start_projection = (truss.start.x - origin.x) * ux + (truss.start.y - origin.y) * uy
                end_projection = (truss.end.x - origin.x) * ux + (truss.end.y - origin.y) * uy
                direction = "forward" if start_projection <= end_projection else "reverse"
                station_map[truss_id] = StationRange(
                    min(start_projection, end_projection), max(start_projection, end_projection), direction)
            return station_map, span

    station_map, cumulative = {}, 0.0
    for index, truss_id in enumerate(ordered):
        truss = lookup[truss_id]
        if not truss.is_line:
            station_map[truss_id] = StationRange(cumulative, cumulative, "connector")
            continue
        neighbour = ordered[index - 1] if index else (ordered[index + 1] if len(ordered) > 1 else None)
        direction = "forward"
        if neighbour:
            _, port = _connection_for(connections, truss_id, neighbour)
            if (index and port == "end") or (not index and port == "start"):
                direction = "reverse"
        length = truss.geometric_length_mm
        station_map[truss_id] = StationRange(cumulative, cumulative + length, direction)
        cumulative += length
    return station_map, cumulative
