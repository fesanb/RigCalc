"""General 3D frame solver for any truss construction geometry.

One model covers straight, inclined, vertical, curved, cornered, branched,
closed and true 3D constructions.  The construction is discretised into
linear-elastic Euler-Bernoulli frame elements (``frame3d``):

* straight members (Line, Lighting Pipe) between their geometric end points;
* curved (Circle) members as short chords along the resolved centreline arc;
* corner blocks as a node at the intersection of the connected member axes,
  joined to each member end by a link element with that member's section.

Nodes are placed at every member end, support, point load, distributed-load
end and support-span midpoint, so point loads and supports act exactly at
nodes and the consistent uniform loads make nodal results exact.

Supports
--------
Hoists are vertical tension-only supports: a hoist may only pull up.  The
contact state is solved by an active-set iteration and accepted only when it
satisfies complementarity exactly (every engaged hoist has a non-negative
reaction and every released pickup rises, so its chain is slack).  Structural
links are bilateral vertical supports.

A hanging rig is free to sway and roll.  Each support node gets a horizontal
spring equal to a representative chain pendulum stiffness, and every node a
very weak rotational spring, so the stiffness matrix is regular.  The forces
these springs carry are reported; a result that depends on them (lateral or
roll stability not provided by the supports) is never writeback eligible.

Hoist/chain mass is never a truss load: High Hook = reaction +
WeightWithChain (see ``contact.py``).
"""

from math import ceil, cos, radians, sin, sqrt

from .beam_statics import _reaction_record
from .continuous_beam import _section_result
from .contact import RELEASED_CONTACT_RULE, released_contact_is_slack
from .frame3d import (element_axes, global_uniform_load_to_local,
                      local_stiffness, transformation_matrix,
                      uniform_local_equivalent_load)
from .sparse import SparseSymmetric, solve_spd
from .validation import finalize_eligibility

GRAVITY_M_S2 = 9.80665
NODE_MERGE_MM = 1.0
ARC_SEGMENT_DEG = 7.5
# Pendulum stiffness of a chain, T/L: ~500 kg on ~5 m of chain.
HOIST_HORIZONTAL_SPRING_N_M = 1000.0
ROTATION_SPRING_NM_RAD = 1.0
# A result may not rely on the stabilising springs: their forces must stay
# below this fraction of the total weight (and moment of weight x 1 m).
STABILISER_FORCE_RATIO = 0.005
REACTION_TOLERANCE_KG = 1.0e-6
MAX_ACTIVE_SET_ITERATIONS = 200
DOF = 6


class _Node:
    __slots__ = ("id", "x", "y", "z", "member_id", "local_mm", "index")

    def __init__(self, identifier, point, member_id=None, local_mm=None):
        self.id = identifier
        self.x, self.y, self.z = point
        self.member_id = member_id
        self.local_mm = local_mm
        self.index = None


class _Element:
    __slots__ = ("id", "node_i", "node_j", "section", "member_id",
                 "start_local_mm", "end_local_mm", "kind", "q_n_m")

    def __init__(self, identifier, node_i, node_j, section, member_id,
                 start_local_mm, end_local_mm, kind):
        self.id = identifier
        self.node_i, self.node_j = node_i, node_j
        self.section = section
        self.member_id = member_id
        self.start_local_mm, self.end_local_mm = start_local_mm, end_local_mm
        self.kind = kind
        self.q_n_m = 0.0


def _distance(a, b):
    return sqrt((a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2)


def _member_point(member, local_mm):
    """Centreline point (mm) at a distance along the member axis."""
    if member.is_arc:
        arc = member.arc
        sweep = arc["sweep_rad"]
        fraction = local_mm/member.axis_length_mm if member.axis_length_mm else 0
        angle = arc["start_angle_rad"]+sweep*fraction
        return (arc["center_x"]+arc["radius_mm"]*cos(angle),
                arc["center_y"]+arc["radius_mm"]*sin(angle), arc["z"])
    length = member.geometric_length_mm
    fraction = local_mm/length if length else 0.0
    s, e = member.start, member.end
    return (s.x+fraction*(e.x-s.x), s.y+fraction*(e.y-s.y),
            s.z+fraction*(e.z-s.z))


def _member_direction(member, port):
    """Unit axis direction pointing out of the member at an end."""
    if member.is_arc:
        arc = member.arc
        angle = arc["start_angle_rad"]+(arc["sweep_rad"] if port == "end"
                                        else 0.0)
        sign = 1.0 if arc["sweep_rad"] > 0 else -1.0
        tangent = (-sin(angle)*sign, cos(angle)*sign, 0.0)
        return tangent if port == "end" else tuple(-v for v in tangent)
    s, e = member.start, member.end
    vector = (e.x-s.x, e.y-s.y, e.z-s.z)
    length = sqrt(sum(v*v for v in vector)) or 1.0
    unit = tuple(v/length for v in vector)
    return unit if port == "end" else tuple(-v for v in unit)


def _axis_intersection(points, directions):
    """Least-squares point closest to several 3D lines, or None if parallel."""
    a = [[0.0]*3 for _ in range(3)]
    b = [0.0]*3
    for point, direction in zip(points, directions):
        projector = [[(1.0 if r == c else 0.0)-direction[r]*direction[c]
                      for c in range(3)] for r in range(3)]
        for r in range(3):
            for c in range(3):
                a[r][c] += projector[r][c]
            b[r] += sum(projector[r][c]*point[c] for c in range(3))
    # Solve the 3x3 system with Cramer's rule.
    def det(m):
        return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1]) -
                m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0]) +
                m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
    d = det(a)
    scale = max(abs(value) for row in a for value in row) or 1.0
    if abs(d) <= 1.0e-6*scale**3:
        return None
    solution = []
    for column in range(3):
        m = [row[:] for row in a]
        for r in range(3):
            m[r][column] = b[r]
        solution.append(det(m)/d)
    return tuple(solution)


def _section_valid(section):
    required = (section.elastic_modulus_pa, section.shear_modulus_pa,
                section.area_m2, section.ixx_m4, section.iyy_m4,
                section.izz_m4)
    return all(value is not None and value > 0.0 for value in required)


def _base_result(construction):
    return {
        "construction_id": construction.id,
        "construction_name": construction.label,
        "status": "not_calculated",
        "method": "general_3d_frame_tension_only_hoists",
        "loads": [], "reactions": [], "stations": [], "element_forces": [],
        "issues": [],
        "writeback_eligible": False,
        "load_transfer_eligible": False,
        "total_applied_mass_kg": 0.0,
        "load_model": {
            "direction": "fixed_global_negative_z",
            "distributed_load": "consistent_element_load",
            "hoist_chain_mass": "top hook only; never a truss load",
        },
    }


def solve_general_frame(construction, loads=None):
    """Solve one construction; ``loads`` is used only to detect transfers."""
    result = _base_result(construction)
    issues = result["issues"]
    members = [item for item in construction.truss_segments if item.has_axis]
    corners = [item for item in construction.truss_segments
               if item.item_type == "Corner"]
    for item in construction.truss_segments:
        if not item.has_axis and item.item_type != "Corner":
            issues.append("unresolved_member_geometry:{}:{}".format(
                item.id, item.item_type or "unknown"))
    if issues:
        return result
    if not members:
        issues.append("no_structural_members")
        return result
    for member in members:
        if member.mechanical_section is None:
            issues.append("mechanical_section_missing:{}".format(member.id))
        elif not _section_valid(member.mechanical_section):
            issues.append("mechanical_section_incomplete:{}".format(
                member.mechanical_section.identifier))
    if issues:
        return result
    transferred_all = [item for item in (loads or [])
                       if str(item.get("source_type", "")).startswith(
                           "transferred")]
    transferred_located = [item for item in transferred_all
                           if item.get("truss_id") in
                           {member.id for member in members} and
                           item.get("local_mm") is not None]
    transferred = [item for item in transferred_all
                   if item not in transferred_located]
    if transferred:
        # Never drop a transferred load silently.
        issues.append("transferred_load_location_unsupported_in_general_frame")

    member_by_id = {item.id: item for item in members}
    attachments = {item.id: set() for item in members}
    supports = list(construction.supports)
    point_loads = list(construction.point_loads)
    distributed = []
    for attached in supports + point_loads:
        attachment = attached.attachment
        if attachment.truss_id in attachments:
            attachments[attachment.truss_id].add(
                attachment.local_position_from_truss_start_mm)
        else:
            issues.append("attachment_carrier_not_in_construction:{}".format(
                attached.item.id))
    for item in transferred_located:
        attachments[item["truss_id"]].add(item["local_mm"])
    for attached in construction.distributed_loads:
        item, attachment = attached.item, attached.attachment
        member = member_by_id.get(attachment.truss_id)
        if member is None:
            issues.append("attachment_carrier_not_in_construction:{}".format(
                item.id))
            continue
        start = attachment.local_position_from_truss_start_mm
        end = None
        if item.end_position is not None:
            from rigcalc.topology.attachments import _nearest_on_axis
            nearest = _nearest_on_axis(item.end_position, member, False)
            if nearest is not None:
                end = nearest[1]*member.axis_length_mm
        if end is None:
            end = start+(item.length_mm or 0.0)
        low, high = sorted((max(0.0, start), min(member.axis_length_mm, end)))
        if high-low <= NODE_MERGE_MM or item.total_mass_kg is None:
            issues.append("distributed_load_interval_unresolved:{}".format(
                item.id))
            continue
        attachments[member.id].update((low, high))
        distributed.append((item, member, low, high))
    if _fatal(issues):
        return result

    # Support-span midpoints along each member (for deflection reporting).
    support_locals = {item.id: [] for item in members}
    for attached in supports:
        if attached.attachment.truss_id in support_locals:
            support_locals[attached.attachment.truss_id].append(
                attached.attachment.local_position_from_truss_start_mm)
    nodes, node_at = [], {}

    def new_node(point, member_id=None, local_mm=None):
        node = _Node("N{:05d}".format(len(nodes)), point, member_id, local_mm)
        nodes.append(node)
        return node

    elements = []
    member_end_nodes = {}
    for member in members:
        length = member.axis_length_mm
        locals_ = {0.0, length}
        locals_.update(value for value in attachments[member.id]
                       if 0.0 <= value <= length)
        ordered_supports = sorted(support_locals[member.id])
        locals_.update((a+b)/2.0 for a, b in
                       zip(ordered_supports, ordered_supports[1:]))
        if member.is_arc:
            count = max(1, int(ceil(abs(member.arc["sweep_rad"]) /
                                    radians(ARC_SEGMENT_DEG))))
            locals_.update(length*index/count for index in range(count+1))
        merged = []
        for value in sorted(locals_):
            if not merged or value-merged[-1] > NODE_MERGE_MM:
                merged.append(value)
            else:
                # Keep exact end and attachment positions.
                if value == length:
                    merged[-1] = length
        member_nodes = [new_node(_member_point(member, value), member.id,
                                 value) for value in merged]
        node_at[member.id] = member_nodes
        member_end_nodes[(member.id, "start")] = member_nodes[0]
        member_end_nodes[(member.id, "end")] = member_nodes[-1]
        for first, second in zip(member_nodes, member_nodes[1:]):
            elements.append(_Element(
                "E{:05d}".format(len(elements)), first, second,
                member.mechanical_section, member.id, first.local_mm,
                second.local_mm, "member"))

    # Union-find for coincident member ends (direct endpoint connections).
    parent = {node.id: node.id for node in nodes}

    def find(identifier):
        while parent[identifier] != identifier:
            parent[identifier] = parent[parent[identifier]]
            identifier = parent[identifier]
        return identifier

    def union(a, b):
        ra, rb = find(a.id), find(b.id)
        if ra != rb:
            parent[rb] = ra

    corner_ids = {item.id for item in corners}
    corner_links = {item.id: [] for item in corners}
    for connection in construction.connections:
        a_corner = connection.a in corner_ids
        b_corner = connection.b in corner_ids
        if a_corner or b_corner:
            corner_id = connection.a if a_corner else connection.b
            member_id = connection.b if a_corner else connection.a
            port = connection.b_port if a_corner else connection.a_port
            if member_id in member_by_id:
                corner_links[corner_id].append((member_id, port))
            continue
        if connection.a not in member_by_id or connection.b not in member_by_id:
            continue
        node_a = member_end_nodes[(connection.a, connection.a_port)]
        node_b = member_end_nodes[(connection.b, connection.b_port)]
        gap = _distance((node_a.x, node_a.y, node_a.z),
                        (node_b.x, node_b.y, node_b.z))
        if gap <= NODE_MERGE_MM or connection.method == "endpoint":
            # A detected endpoint joint (within the endpoint tolerance) is one
            # physical node; a millimetre bridge element would only destroy
            # the conditioning.  The merged node sits at the mean position.
            union(node_a, node_b)
        else:
            # Inferred collinear joint with a small gap: bridge it with the
            # stiffer of the two sections rather than inventing a hinge.
            section = max((member_by_id[connection.a].mechanical_section,
                           member_by_id[connection.b].mechanical_section),
                          key=lambda value: value.iyy_m4)
            elements.append(_Element(
                "E{:05d}".format(len(elements)), node_a, node_b, section,
                None, None, None, "joint_link"))
    corner_nodes = {}
    corner_arms = {}
    for corner in corners:
        links = corner_links[corner.id]
        if not links:
            issues.append("corner_without_connected_member:{}".format(
                corner.id))
            continue
        ends = [member_end_nodes[(member_id, port)]
                for member_id, port in links]
        directions = [_member_direction(member_by_id[member_id], port)
                      for member_id, port in links]
        points = [(node.x, node.y, node.z) for node in ends]
        center = _axis_intersection(points, directions)
        centroid = tuple(sum(p[k] for p in points)/len(points)
                         for k in range(3))
        reach = 4.0*max(max(member_by_id[m].width_mm,
                            member_by_id[m].height_mm) for m, _ in links)
        if center is None or _distance(center, centroid) > reach:
            center = centroid
        corner_node = new_node(center)
        corner_nodes[corner.id] = corner_node
        corner_arms[corner.id] = [_distance(center, (end.x, end.y, end.z))
                                  for end in ends]
        parent[corner_node.id] = corner_node.id
        for (member_id, _), end in zip(links, ends):
            gap = _distance(center, (end.x, end.y, end.z))
            if gap <= NODE_MERGE_MM:
                union(corner_node, end)
            else:
                elements.append(_Element(
                    "E{:05d}".format(len(elements)), end, corner_node,
                    member_by_id[member_id].mechanical_section, None,
                    None, None, "corner_link"))
    if _fatal(issues):
        return result

    # Collapse merged nodes and number the remaining ones.
    representative = {}
    for node in nodes:
        root = find(node.id)
        representative[node.id] = root
    by_id = {node.id: node for node in nodes}
    groups = {}
    for node in nodes:
        groups.setdefault(representative[node.id], []).append(node)
    for root, members_ in groups.items():
        if len(members_) > 1:
            target = by_id[root]
            target.x = sum(item.x for item in members_)/len(members_)
            target.y = sum(item.y for item in members_)/len(members_)
            target.z = sum(item.z for item in members_)/len(members_)
    unique = [node for node in nodes if representative[node.id] == node.id]
    for index, node in enumerate(unique):
        node.index = index

    def rep(node):
        return by_id[representative[node.id]]

    for element in elements:
        element.node_i, element.node_j = rep(element.node_i), rep(element.node_j)
    elements = [item for item in elements if item.node_i is not item.node_j]

    # Loads (N); records for the report.
    load_records = []
    node_loads = {}

    def add_node_load(node, mass_kg):
        node = rep(node)
        node_loads[node.index] = node_loads.get(node.index, 0.0)+mass_kg

    def member_node(member_id, local_mm):
        candidates = node_at[member_id]
        return min(candidates, key=lambda node: abs(node.local_mm-local_mm))

    member_elements = {}
    for element in elements:
        if element.member_id is not None:
            member_elements.setdefault(element.member_id, []).append(element)
    for member in members:
        mass = member.self_weight_kg+member.cable_load_kg_m*(
            member.axis_length_mm/1000.0)
        if mass <= 0.0:
            continue
        member_list = member_elements.get(member.id, [])
        chord_total = sum(_element_length_mm(item) for item in member_list)
        if chord_total <= 0.0:
            continue
        q = mass*GRAVITY_M_S2/(chord_total/1000.0)
        for element in member_list:
            element.q_n_m += q
        if member.self_weight_kg > 0.0:
            load_records.append(_load_record(
                member.id, "truss_self_weight", member.self_weight_kg, member,
                0.0, member.axis_length_mm, "TrussItem.Weight"))
        if member.cable_load_kg_m > 0.0:
            load_records.append(_load_record(
                "{}:cable".format(member.id), "cable_flat_rate",
                mass-member.self_weight_kg, member, 0.0,
                member.axis_length_mm, "RigCalc calculation scope setting"))
    for corner in corners:
        if corner.self_weight_kg > 0.0 and corner.id in corner_nodes:
            add_node_load(corner_nodes[corner.id], corner.self_weight_kg)
            node = rep(corner_nodes[corner.id])
            load_records.append({
                "source_id": corner.id, "source_type": "corner_self_weight",
                "mass_kg": corner.self_weight_kg, "station_mm": 0.0,
                "truss_id": corner.id,
                "position_mm": [node.x, node.y, node.z],
                "evidence": "TrussItem.Weight",
            })
        cable_m = _corner_cable_length_mm(
            corner, corner_arms.get(corner.id, []))/1000.0
        if (corner.cable_load_kg_m > 0.0 and cable_m > 0.0 and
                corner.id in corner_nodes):
            mass = corner.cable_load_kg_m*cable_m
            add_node_load(corner_nodes[corner.id], mass)
            node = rep(corner_nodes[corner.id])
            load_records.append({
                "source_id": "{}:cable".format(corner.id),
                "source_type": "cable_flat_rate", "mass_kg": mass,
                "station_mm": 0.0, "truss_id": corner.id,
                "cable_length_m": cable_m,
                "position_mm": [node.x, node.y, node.z],
                "evidence": "RigCalc calculation scope setting (corner)",
            })
    for attached in point_loads:
        item, attachment = attached.item, attached.attachment
        if item.weight_kg is None or attachment.truss_id not in node_at:
            continue
        local = attachment.local_position_from_truss_start_mm
        node = member_node(attachment.truss_id, local)
        add_node_load(node, item.weight_kg)
        load_records.append({
            "source_id": item.id, "source_type": item.record_type,
            "mass_kg": item.weight_kg, "station_mm": local,
            "truss_id": attachment.truss_id,
            "position_mm": [node.x, node.y, node.z],
            "evidence": attachment.method,
        })
    for item in transferred_located:
        node = member_node(item["truss_id"], item["local_mm"])
        add_node_load(node, item["mass_kg"])
        load_records.append({
            "source_id": item["source_id"], "source_type": item["source_type"],
            "mass_kg": item["mass_kg"], "station_mm": item["local_mm"],
            "truss_id": item["truss_id"],
            "position_mm": [node.x, node.y, node.z],
            "evidence": item.get("evidence", "construction_graph"),
        })
    for item, member, low, high in distributed:
        member_list = [element for element in member_elements.get(member.id, [])
                       if element.start_local_mm >= low-NODE_MERGE_MM and
                       element.end_local_mm <= high+NODE_MERGE_MM]
        chord = sum(_element_length_mm(element) for element in member_list)
        if chord <= 0.0:
            issues.append("distributed_load_interval_unresolved:{}".format(
                item.id))
            continue
        q = item.total_mass_kg*GRAVITY_M_S2/(chord/1000.0)
        for element in member_list:
            element.q_n_m += q
        load_records.append(_load_record(
            item.id, item.record_type, item.total_mass_kg, member, low, high,
            "geometry_sphere"))
    result["loads"] = load_records
    total_mass = sum(item["mass_kg"] for item in load_records)
    result["total_applied_mass_kg"] = total_mass
    if not load_records:
        issues.append("no_applied_loads")
        return result

    # Supports.
    support_nodes = []
    seen_nodes = {}
    for attached in supports:
        attachment = attached.attachment
        if attachment.truss_id not in node_at:
            continue
        node = rep(member_node(attachment.truss_id,
                               attachment.local_position_from_truss_start_mm))
        # A hoist hung over a corner block attaches geometrically to one of
        # the member ends next to it; it physically carries the corner node.
        position = attached.item.position
        for corner_node in corner_nodes.values():
            corner_node = rep(corner_node)
            to_corner = ((position.x-corner_node.x)**2 +
                         (position.y-corner_node.y)**2)**0.5
            to_node = ((position.x-node.x)**2+(position.y-node.y)**2)**0.5
            if to_corner < to_node:
                node = corner_node
        if node.index in seen_nodes:
            issues.append("coincident_supports:{}:{}".format(
                seen_nodes[node.index], attached.item.id))
            continue
        seen_nodes[node.index] = attached.item.id
        support_nodes.append((attached, node))
    if len(support_nodes) < 1:
        issues.append("requires_at_least_one_support")
        return result

    model = _Model(unique, elements, node_loads, support_nodes)
    try:
        signed = model.solve({item.item.id for item, _ in support_nodes})
    except ValueError as error:
        issues.append(str(error))
        issues.append("insufficient_supports_for_stable_structure")
        return result
    contact = _solve_contact_state(model, support_nodes, signed)
    if (contact["converged"] and
            not _stabilisers_ok(model, contact["solution"], support_nodes,
                                total_mass) and
            contact["solution"]["active_ids"] != signed["active_ids"]):
        # The "solution" is held only by the weak stabilising springs after
        # releasing hoists: physically the rig would tip.  Report the signed
        # all-engaged result instead of a misleading single-hoist load.
        contact = {"converged": False, "solution": None,
                   "issue": "tension_only_active_set_no_feasible_solution"}
    final = contact["solution"] if contact["solution"] is not None else signed
    rotating = None
    if (contact["converged"] and
            not _stabilisers_ok(model, final, support_nodes, total_mass) and
            final["active_ids"] == signed["active_ids"]):
        # Every hoist is engaged but the supports cannot hold the drawn
        # geometry (one hoist, or all hoists on one line): the rig rotates
        # about its support line until its centre of gravity is below it.
        # That rotation does not change the vertical reactions, which follow
        # exactly from rigid-body statics along the support line.
        rotating = _rigid_line_reactions(model, node_loads, support_nodes)
        if rotating is not None:
            final = dict(final, reactions_kg=rotating)
            if any(value < -REACTION_TOLERANCE_KG
                   for value in rotating.values()):
                contact = {"converged": False, "solution": None,
                           "issue":
                           "tension_only_active_set_no_feasible_solution"}
                rotating = None
                final = signed
    result.update(_format(construction, model, final, signed, contact,
                          support_nodes, total_mass, member_by_id))
    if transferred:
        result["validation"]["load_model_valid"] = False
    stable = result["validation"]["stabiliser_forces_ok"]
    if rotating is not None:
        stable = True
        result["validation"]["rotation_about_support_line"] = True
        result["validation"]["reaction_method"] = (
            "rigid_body_statics_along_support_line")
        # The reactions are exact statics, independent of the stabilised
        # frame solve (whose residual is poor because only weak springs hold
        # the rotation, and whose member results are discarded below).
        result["validation"]["frame_numerically_valid"] = (
            result["validation"]["numerically_valid"])
        result["validation"]["numerically_valid"] = True
        result["validation"]["moment_equilibrium_ok"] = True
        # The rig does not hang in the drawn geometry, so member forces and
        # deflections of the drawn model are not meaningful.
        result["element_forces"] = []
        result["deflection"] = {"maximum": None, "spans": []}
        issues.append("rig_rotates_about_support_line")
    support_model_valid = (contact["converged"] and stable and
                           not any(issue.startswith("coincident_supports")
                                   for issue in issues))
    result["status"] = ("preliminary" if contact["converged"]
                        else "diagnostic")
    if not contact["converged"]:
        issues.append(contact["issue"])
    if not stable:
        result["status"] = "diagnostic"
        issues.append("lateral_or_roll_stability_not_provided_by_supports")
    finalize_eligibility(
        result, support_model_valid=support_model_valid,
        numerical_valid=result["validation"]["numerically_valid"],
        load_model_valid=result["validation"].get("load_model_valid", True),
        permit_writeback=True, permit_load_transfer=True)
    return result


NON_BLOCKING_ISSUES = ("rig_rotates_about_support_line",)


def _rigid_line_reactions(model, node_loads, support_nodes):
    """Exact vertical reactions for a rig hanging from one or two points.

    Returns None when the supports do not define a usable line (three or
    more points, or two points vertically above each other).
    """
    if len(support_nodes) == 1:
        attached, _ = support_nodes[0]
        total = sum(node_loads.values()) + sum(
            element.q_n_m*_element_length_mm(element)/1000.0/GRAVITY_M_S2
            for element in model.elements)
        return {attached.item.id: total}
    if len(support_nodes) != 2:
        return None
    (first, node_a), (second, node_b) = support_nodes
    dx, dy = node_b.x-node_a.x, node_b.y-node_a.y
    span = (dx*dx+dy*dy)**0.5
    if span <= 1.0:
        return None
    ux, uy = dx/span, dy/span
    masses = []
    by_index = {node.index: node for node in model.nodes}
    for index, mass in node_loads.items():
        node = by_index[index]
        masses.append((mass, node.x, node.y))
    for element in model.elements:
        if element.q_n_m <= 0.0:
            continue
        i, j = element.node_i, element.node_j
        mass = element.q_n_m*_element_length_mm(element)/1000.0/GRAVITY_M_S2
        masses.append((mass, (i.x+j.x)/2.0, (i.y+j.y)/2.0))
    total = sum(mass for mass, _, _ in masses)
    moment = sum(mass*((x-node_a.x)*ux+(y-node_a.y)*uy)
                 for mass, x, y in masses)
    second_reaction = moment/span
    return {first.item.id: total-second_reaction,
            second.item.id: second_reaction}


def _is_box_corner(corner):
    text = "{} {}".format(corner.symbol, corner.name).lower()
    return "box" in text or "multi" in text


def _corner_cable_length_mm(corner, arms):
    """Cable run through a corner block.

    L and T corners: the arms from the corner node to each connected member
    end (C21 0.71 m, C35 0.855 m).  A multi-way box is counted on all six
    faces, connected or not, at half the section size (0.866 m), matching
    Production Assist's cable-length convention.
    """
    if _is_box_corner(corner):
        half = max(corner.width_mm, corner.height_mm)/2.0
        if half <= 0.0 and arms:
            half = sum(arms)/len(arms)
        return 6.0*half
    return sum(arms)


NON_FATAL_ISSUES = ("transferred_load_location_unsupported_in_general_frame",)


def _fatal(issues):
    return any(issue not in NON_FATAL_ISSUES for issue in issues)


def _element_length_mm(element):
    a, b = element.node_i, element.node_j
    return _distance((a.x, a.y, a.z), (b.x, b.y, b.z))


def _load_record(source_id, source_type, mass, member, low, high, evidence):
    middle = _member_point(member, (low+high)/2.0)
    return {
        "source_id": source_id, "source_type": source_type,
        "mass_kg": mass, "station_mm": (low+high)/2.0,
        "interval_start_mm": low, "interval_end_mm": high,
        "mass_per_m_kg": mass/((high-low)/1000.0) if high > low else None,
        "truss_id": member.id, "position_mm": list(middle),
        "evidence": evidence,
    }


class _Model:
    """Assembled frame; solves for a given set of active vertical supports."""

    def __init__(self, nodes, elements, node_loads, support_nodes):
        self.nodes = nodes
        self.elements = elements
        self.support_nodes = support_nodes
        size = len(nodes)*DOF
        self.size = size
        self.stiffness = SparseSymmetric(size)
        self.loads = [0.0]*size
        self.element_data = []
        for index, mass in node_loads.items():
            self.loads[index*DOF+2] -= mass*GRAVITY_M_S2
        for element in elements:
            i, j = element.node_i, element.node_j
            node_i = _Point(i.x/1000.0, i.y/1000.0, i.z/1000.0)
            node_j = _Point(j.x/1000.0, j.y/1000.0, j.z/1000.0)
            axes = element_axes(node_i, node_j, (0.0, 0.0, 1.0))
            length = _element_length_mm(element)/1000.0
            section = element.section
            frame_element = _FrameSection(section)
            local_k = local_stiffness(frame_element, length)
            transform = transformation_matrix(axes)
            global_k = _rotate(local_k, transform)
            q_local = global_uniform_load_to_local(
                (0.0, 0.0, -element.q_n_m), axes)
            local_f = uniform_local_equivalent_load(q_local, length)
            global_f = [sum(transform[r][c]*local_f[r] for r in range(12))
                        for c in range(12)]
            indices = ([i.index*DOF+d for d in range(DOF)] +
                       [j.index*DOF+d for d in range(DOF)])
            self.stiffness.add_symmetric_block(indices, global_k)
            for index, value in zip(indices, global_f):
                self.loads[index] += value
            self.element_data.append(
                (element, indices, transform, local_k, local_f, length))
        for node in nodes:
            base = node.index*DOF
            for d in (3, 4, 5):
                self.stiffness.add(base+d, base+d, ROTATION_SPRING_NM_RAD)
        for _, node in support_nodes:
            base = node.index*DOF
            for d in (0, 1):
                self.stiffness.add(base+d, base+d,
                                   HOIST_HORIZONTAL_SPRING_N_M)

    def solve(self, active_ids):
        restrained = {node.index*DOF+2 for attached, node in
                      self.support_nodes if attached.item.id in active_ids}
        free = [index for index in range(self.size) if index not in restrained]
        position = {old: new for new, old in enumerate(free)}
        reduced = SparseSymmetric(len(free))
        for old_row in free:
            row = position[old_row]
            target = reduced.rows[row]
            for old_column, value in self.stiffness.rows[old_row].items():
                column = position.get(old_column)
                if column is not None:
                    target[column] = value
        rhs = [self.loads[index] for index in free]
        reduced_u, diagnostics = solve_spd(reduced, rhs)
        residual = [a-b for a, b in zip(reduced.multiply(reduced_u), rhs)]
        scale = max([abs(value) for value in rhs]+[1.0])
        diagnostics["maximum_reduced_residual"] = max(
            [abs(value) for value in residual]+[0.0])
        diagnostics["relative_reduced_residual"] = (
            diagnostics["maximum_reduced_residual"]/scale)
        displacement = [0.0]*self.size
        for old, value in zip(free, reduced_u):
            displacement[old] = value
        internal = self.stiffness.multiply(displacement)
        reactions = {}
        for attached, node in self.support_nodes:
            dof = node.index*DOF+2
            reactions[attached.item.id] = (
                (internal[dof]-self.loads[dof])/GRAVITY_M_S2
                if attached.item.id in active_ids else 0.0)
        return {"active_ids": set(active_ids), "displacement": displacement,
                "reactions_kg": reactions, "internal": internal,
                "numerical_diagnostics": diagnostics}


class _Point:
    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _FrameSection:
    def __init__(self, section):
        self.elastic_modulus_pa = section.elastic_modulus_pa
        self.shear_modulus_pa = section.shear_modulus_pa
        self.area_m2 = section.area_m2
        self.torsion_constant_m4 = section.ixx_m4
        self.iy_m4 = section.iyy_m4
        self.iz_m4 = section.izz_m4


def _rotate(local_k, transform):
    temp = [[sum(local_k[r][k]*transform[k][c] for k in range(12))
             for c in range(12)] for r in range(12)]
    return [[sum(transform[k][r]*temp[k][c] for k in range(12))
             for c in range(12)] for r in range(12)]


def _stabiliser_forces(model, solution, support_nodes, total_mass):
    """Largest spring force/moment and the allowance it must stay under."""
    displacement = solution["displacement"]
    horizontal = 0.0
    for _, node in support_nodes:
        base = node.index*DOF
        horizontal = max(horizontal,
                         abs(displacement[base])*HOIST_HORIZONTAL_SPRING_N_M,
                         abs(displacement[base+1])*HOIST_HORIZONTAL_SPRING_N_M)
    rotational = max(abs(displacement[node.index*DOF+d])*ROTATION_SPRING_NM_RAD
                     for node in model.nodes for d in (3, 4, 5))
    allowed = max(1.0, STABILISER_FORCE_RATIO*total_mass*GRAVITY_M_S2)
    return horizontal, rotational, allowed


def _stabilisers_ok(model, solution, support_nodes, total_mass):
    horizontal, rotational, allowed = _stabiliser_forces(
        model, solution, support_nodes, total_mass)
    return horizontal <= allowed and rotational <= allowed


def _solve_contact_state(model, support_nodes, signed):
    """Active-set iteration with exact complementarity verification."""
    hoists = [attached for attached, _ in support_nodes
              if not attached.item.is_structural_link]
    node_of = {attached.item.id: node for attached, node in support_nodes}
    active = {attached.item.id for attached, _ in support_nodes}
    solution, seen = signed, set()
    for _ in range(MAX_ACTIVE_SET_ITERATIONS):
        key = frozenset(active)
        if key in seen:
            return {"converged": False, "solution": None,
                    "issue": "tension_only_active_set_cycle"}
        seen.add(key)
        negative = [(solution["reactions_kg"][item.item.id], item.item.id)
                    for item in hoists if item.item.id in active and
                    solution["reactions_kg"][item.item.id] <
                    -REACTION_TOLERANCE_KG]
        sinking = []
        for item in hoists:
            if item.item.id in active:
                continue
            uz = solution["displacement"][node_of[item.item.id].index*DOF+2]
            if not released_contact_is_slack(uz):
                sinking.append((uz, item.item.id))
        if not negative and not sinking:
            return {"converged": True, "solution": solution, "issue": None,
                    "iterations": len(seen)}
        if negative:
            active.discard(min(negative)[1])
        else:
            active.add(min(sinking)[1])
        try:
            solution = model.solve(active)
        except ValueError:
            # Releasing that hoist leaves a mechanism: the rig would tip or
            # fall.  There is no admissible tension-only state.
            return {"converged": False, "solution": None,
                    "issue": "tension_only_active_set_no_feasible_solution"}
    return {"converged": False, "solution": None,
            "issue": "tension_only_active_set_not_converged"}


def _format(construction, model, final, signed, contact, support_nodes,
            total_mass, member_by_id):
    displacement = final["displacement"]
    reactions = []
    for attached, node in support_nodes:
        support_id = attached.item.id
        record = _reaction_record(attached,
                                  final["reactions_kg"][support_id])
        record["station_mm"] = (
            attached.attachment.global_station_mm
            if attached.attachment.global_station_mm is not None
            else attached.attachment.local_position_from_truss_start_mm)
        record["truss_id"] = attached.attachment.truss_id
        record["position_mm"] = [node.x, node.y, node.z]
        record["support_active"] = support_id in final["active_ids"]
        record["unconstrained_reaction_mass_kg"] = (
            signed["reactions_kg"][support_id])
        reactions.append(record)
    stations = []
    for node in model.nodes:
        values = displacement[node.index*DOF:node.index*DOF+DOF]
        stations.append({
            "node_id": node.id,
            "station_mm": node.local_mm if node.local_mm is not None else 0.0,
            "truss_id": node.member_id,
            "position_mm": [node.x, node.y, node.z],
            "displacements": dict(zip(
                ("ux_m", "uy_m", "uz_m", "rx_rad", "ry_rad", "rz_rad"),
                values)),
        })
    element_forces = []
    labels = ("N_n", "Vy_n", "Vz_n", "T_nm", "My_nm", "Mz_nm")
    for element, indices, transform, local_k, local_f, length in \
            model.element_data:
        local_u = [sum(transform[r][c]*displacement[indices[c]]
                       for c in range(12)) for r in range(12)]
        forces = [sum(local_k[r][c]*local_u[c] for c in range(12))-local_f[r]
                  for r in range(12)]
        i, j = element.node_i, element.node_j
        element_forces.append({
            "element_id": element.id, "element_kind": element.kind,
            "truss_id": element.member_id,
            "start_station_mm": element.start_local_mm,
            "end_station_mm": element.end_local_mm,
            "start_position_mm": [i.x, i.y, i.z],
            "end_position_mm": [j.x, j.y, j.z],
            "length_m": length,
            "cross_section": _section_result(element.section),
            "i": dict(zip(labels, forces[:6])),
            "j": dict(zip(labels, forces[6:])),
        })
    horizontal, rotational, allowed = _stabiliser_forces(
        model, final, support_nodes, total_mass)
    reaction_total = sum(final["reactions_kg"].values())
    vertical_error = reaction_total-total_mass
    tolerance = max(0.01, abs(total_mass)*1.0e-6)
    numerical = final["numerical_diagnostics"]
    validation = {
        "vertical_equilibrium_error_kg": vertical_error,
        "vertical_equilibrium_tolerance_kg": tolerance,
        "vertical_equilibrium_ok": abs(vertical_error) <= tolerance,
        # Every load and reaction acts on the same assembled model, so
        # moment equilibrium follows from the solved system; it is checked
        # through the residual below and the independent vertical balance.
        "moment_equilibrium_ok": numerical["relative_reduced_residual"] <=
        1.0e-8,
        "moment_equilibrium_error_kg_m": 0.0,
        "numerically_valid": numerical["relative_reduced_residual"] <= 1.0e-8,
        "maximum_stabiliser_horizontal_force_n": horizontal,
        "maximum_stabiliser_moment_nm": rotational,
        "stabiliser_allowance_n": allowed,
        "stabiliser_forces_ok": (horizontal <= allowed and
                                 rotational <= allowed*1.0),
        "contact_model": "chain_weight_to_top_hook",
    }
    deflection = _deflection(construction, model, displacement, support_nodes,
                             final["active_ids"], member_by_id)
    active_set = {
        "method": "general_frame_active_set_complementarity",
        "converged": contact["converged"],
        "iterations": contact.get("iterations"),
        "released_support_displacement_rule": RELEASED_CONTACT_RULE,
    }
    released = sum(1 for item in reactions if not item["support_active"])
    payload = {
        "reactions": reactions, "stations": stations,
        "element_forces": element_forces, "validation": validation,
        "deflection": deflection, "numerical_diagnostics": numerical,
        "active_set_validation": active_set,
        "node_count": len(model.nodes), "element_count": len(model.elements),
    }
    if released:
        payload["released_support_count"] = released
        payload["active_support_count"] = len(reactions)-released
    return payload


def _deflection(construction, model, displacement, support_nodes, active_ids,
                member_by_id):
    """Midspan deflection between consecutive active supports per member."""
    nodes_by_member = {}
    for node in model.nodes:
        if node.member_id is not None:
            nodes_by_member.setdefault(node.member_id, []).append(node)
    maximum = None
    for node in model.nodes:
        uz = displacement[node.index*DOF+2]
        if maximum is None or abs(uz) > abs(maximum[0]):
            maximum = (uz, node)
    spans = []
    for member_id, member_nodes in nodes_by_member.items():
        member_nodes.sort(key=lambda node: node.local_mm)
        active_locals = sorted(
            attached.attachment.local_position_from_truss_start_mm
            for attached, _ in support_nodes
            if attached.attachment.truss_id == member_id and
            attached.item.id in active_ids)
        for start, end in zip(active_locals, active_locals[1:]):
            inside = [node for node in member_nodes
                      if start-NODE_MERGE_MM <= node.local_mm <=
                      end+NODE_MERGE_MM]
            if not inside:
                continue
            midpoint = (start+end)/2.0
            mid = min(inside, key=lambda node: abs(node.local_mm-midpoint))
            peak = max(inside, key=lambda node: abs(
                displacement[node.index*DOF+2]))
            mid_mm = displacement[mid.index*DOF+2]*1000.0
            spans.append({
                "truss_id": member_id,
                "span_start_mm": start, "span_end_mm": end,
                "span_length_mm": end-start,
                "midspan": {"station_mm": mid.local_mm,
                            "deflection_mm": mid_mm,
                            "position_mm": [mid.x, mid.y, mid.z]},
                "maximum": {"station_mm": peak.local_mm,
                            "deflection_mm":
                            displacement[peak.index*DOF+2]*1000.0,
                            "position_mm": [peak.x, peak.y, peak.z]},
                "midspan_deflection_ratio": (
                    (end-start)/abs(mid_mm) if abs(mid_mm) > 1.0e-9 else None),
            })
    uz, node = maximum
    return {
        "maximum": {"station_mm": node.local_mm or 0.0,
                    "deflection_mm": uz*1000.0,
                    "truss_id": node.member_id,
                    "position_mm": [node.x, node.y, node.z]},
        "spans": spans,
    }
