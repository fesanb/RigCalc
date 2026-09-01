"""Dependency-free geometrically nonlinear 2D corotational frame solver.

The model uses global horizontal/vertical translations and in-plane rotation.
Roller supports therefore restrain vertical motion while retaining horizontal
movement. Newton iterations use a numerically consistent tangent and load
stepping, keeping this experimental solver separate from Vectorworks code.
"""

from dataclasses import dataclass, field
from math import atan2, hypot

from .linalg import solve_linear_system


@dataclass
class CorotationalNode:
    id: str
    x: float
    z: float
    restrained: tuple = (False, False, False)
    load: tuple = (0.0, 0.0, 0.0)


@dataclass
class CorotationalElement:
    id: str
    node_i: str
    node_j: str
    elastic_modulus_pa: float
    area_m2: float
    inertia_m4: float


@dataclass
class CorotationalCable:
    """Axial, tension-only cable between a fixed motor point and a truss."""
    id: str
    node_i: str
    node_j: str
    axial_stiffness_n_m: float
    unstretched_length_m: float


@dataclass
class CorotationalModel:
    nodes: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    cables: list = field(default_factory=list)


def _element_state(element, node_i, node_j, displacement):
    xi, zi = node_i.x, node_i.z
    xj, zj = node_j.x, node_j.z
    ui, wi, ri, uj, wj, rj = displacement
    dx0, dz0 = xj-xi, zj-zi
    length0 = hypot(dx0, dz0)
    dx, dz = xj+uj-xi-ui, zj+wj-zi-wi
    length = hypot(dx, dz)
    if length0 <= 1.0e-12 or length <= 1.0e-12:
        raise ValueError("zero_length_element")
    c, s = dx/length, dz/length
    chord_rotation = atan2(dz, dx)-atan2(dz0, dx0)
    theta_i, theta_j = ri-chord_rotation, rj-chord_rotation
    axial = element.elastic_modulus_pa*element.area_m2*(length-length0)/length0
    bending = 2.0*element.elastic_modulus_pa*element.inertia_m4/length0
    moment_i = bending*(2.0*theta_i+theta_j)
    moment_j = bending*(theta_i+2.0*theta_j)
    basic = (axial, moment_i, moment_j)
    transform = (
        (-c, -s, 0.0, c, s, 0.0),
        (-s/length, c/length, 1.0, s/length, -c/length, 0.0),
        (-s/length, c/length, 0.0, s/length, -c/length, 1.0),
    )
    global_force = [
        sum(transform[row][column]*basic[row] for row in range(3))
        for column in range(6)]
    shear = (moment_i+moment_j)/length
    return {
        "global_force": global_force, "length_m": length,
        "axial_n": axial, "shear_n": shear,
        "moment_i_nm": moment_i, "moment_j_nm": moment_j,
    }


def _element_force(element, node_i, node_j, displacement):
    return _element_state(
        element, node_i, node_j, displacement)["global_force"]


def _cable_state(cable, node_i, node_j, displacement):
    ui, wi, _, uj, wj, _ = displacement
    dx = node_j.x+uj-node_i.x-ui
    dz = node_j.z+wj-node_i.z-wi
    length = hypot(dx, dz)
    if length <= 1.0e-12:
        raise ValueError("zero_length_cable")
    extension = length-cable.unstretched_length_m
    tension = max(0.0, cable.axial_stiffness_n_m*extension)
    c, s = dx/length, dz/length
    return {
        # The corotational residual uses the same internal-force sign
        # convention as the frame elements: a taut vertical cable supplies a
        # negative-z resisting force at its lower node.
        "global_force": (-tension*c, -tension*s, 0.0,
                         tension*c, tension*s, 0.0),
        "length_m": length, "extension_m": extension,
        "tension_n": tension, "active": extension >= 0.0,
    }


def _cable_force(cable, node_i, node_j, displacement):
    return _cable_state(cable, node_i, node_j, displacement)["global_force"]


def _internal_force(model, displacement, order):
    nodes = {node.id: node for node in model.nodes}
    result = [0.0]*len(displacement)
    for element in model.elements:
        indices = ([3*order[element.node_i]+dof for dof in range(3)] +
                   [3*order[element.node_j]+dof for dof in range(3)])
        force = _element_force(
            element, nodes[element.node_i], nodes[element.node_j],
            [displacement[index] for index in indices])
        for index, value in zip(indices, force):
            result[index] += value
    for cable in model.cables:
        indices = ([3*order[cable.node_i]+dof for dof in range(3)] +
                   [3*order[cable.node_j]+dof for dof in range(3)])
        force = _cable_force(
            cable, nodes[cable.node_i], nodes[cable.node_j],
            [displacement[index] for index in indices])
        for index, value in zip(indices, force):
            result[index] += value
    return result


def _numerical_tangent(model, displacement, order, free):
    tangent = [[0.0]*len(free) for _ in free]
    free_order = {dof: index for index, dof in enumerate(free)}
    nodes = {node.id: node for node in model.nodes}
    for element in model.elements:
        indices = ([3*order[element.node_i]+dof for dof in range(3)] +
                   [3*order[element.node_j]+dof for dof in range(3)])
        local_u = [displacement[index] for index in indices]
        for local_column, global_column in enumerate(indices):
            column = free_order.get(global_column)
            if column is None:
                continue
            step = 1.0e-7*max(1.0, abs(local_u[local_column]))
            plus, minus = list(local_u), list(local_u)
            plus[local_column] += step
            minus[local_column] -= step
            force_plus = _element_force(
                element, nodes[element.node_i], nodes[element.node_j], plus)
            force_minus = _element_force(
                element, nodes[element.node_i], nodes[element.node_j], minus)
            for local_row, global_row in enumerate(indices):
                row = free_order.get(global_row)
                if row is not None:
                    tangent[row][column] += (
                        force_plus[local_row]-force_minus[local_row])/(2.0*step)
    for cable in model.cables:
        indices = ([3*order[cable.node_i]+dof for dof in range(3)] +
                   [3*order[cable.node_j]+dof for dof in range(3)])
        local_u = [displacement[index] for index in indices]
        for local_column, global_column in enumerate(indices):
            column = free_order.get(global_column)
            if column is None:
                continue
            step = 1.0e-7*max(1.0, abs(local_u[local_column]))
            plus, minus = list(local_u), list(local_u)
            plus[local_column] += step
            minus[local_column] -= step
            force_plus = _cable_force(cable, nodes[cable.node_i],
                                      nodes[cable.node_j], plus)
            force_minus = _cable_force(cable, nodes[cable.node_i],
                                       nodes[cable.node_j], minus)
            for local_row, global_row in enumerate(indices):
                row = free_order.get(global_row)
                if row is not None:
                    tangent[row][column] += (
                        force_plus[local_row]-force_minus[local_row])/(2.0*step)
    return tangent


def solve_corotational(model, initial_load_step=0.1, minimum_load_step=0.0025,
                       maximum_load_step=0.25, max_iterations=35,
                       tolerance=1.0e-8, progress=None):
    order = {node.id: index for index, node in enumerate(model.nodes)}
    size = 3*len(model.nodes)
    external = [0.0]*size
    restrained = set()
    for node in model.nodes:
        base = 3*order[node.id]
        for dof, value in enumerate(node.load):
            external[base+dof] = value
        restrained.update(base+dof for dof, fixed in enumerate(node.restrained)
                          if fixed)
    free = [index for index in range(size) if index not in restrained]
    displacement = [0.0]*size
    converged = False
    iterations = 0
    completed_factor = 0.0
    load_step = initial_load_step
    load_history = []
    while completed_factor < 1.0-1.0e-12:
        trial_factor = min(1.0, completed_factor+load_step)
        target = [value*trial_factor for value in external]
        start_displacement = list(displacement)
        step_converged = False
        step_iterations = 0
        for _ in range(max_iterations):
            iterations += 1
            step_iterations += 1
            internal = _internal_force(model, displacement, order)
            residual = [target[index]-internal[index] for index in free]
            reference = max([abs(target[index]) for index in free] + [1.0])
            residual_norm = max([abs(value) for value in residual] + [0.0])
            if progress:
                progress({"load_factor": trial_factor,
                          "iteration": step_iterations,
                          "residual": residual_norm})
            if residual_norm <= tolerance*reference:
                step_converged = True
                break
            tangent = _numerical_tangent(model, displacement, order, free)
            try:
                correction = solve_linear_system(tangent, residual)
            except ValueError:
                break
            accepted = False
            scale = 1.0
            for _line_search in range(9):
                trial = list(displacement)
                for index, value in zip(free, correction):
                    trial[index] += scale*value
                trial_internal = _internal_force(model, trial, order)
                trial_norm = max([
                    abs(target[index]-trial_internal[index])
                    for index in free] + [0.0])
                # A cable that is exactly at its slack/taut boundary has a
                # one-sided tangent.  Accept an equal-norm first trial so
                # the following Newton step can enter the taut branch.
                if trial_norm <= residual_norm*(1.0+1.0e-12):
                    displacement = trial
                    accepted = True
                    break
                scale *= 0.5
            if not accepted:
                break
        if step_converged:
            completed_factor = trial_factor
            load_history.append({
                "load_factor": completed_factor,
                "iterations": step_iterations,
                "load_step": load_step,
            })
            converged = completed_factor >= 1.0-1.0e-12
            if step_iterations <= 6:
                load_step = min(maximum_load_step, load_step*1.5)
        else:
            displacement = start_displacement
            load_step *= 0.5
            if load_step < minimum_load_step:
                break
    internal = _internal_force(model, displacement, order)
    nodes = {node.id: node for node in model.nodes}
    element_results = []
    for element in model.elements:
        indices = ([3*order[element.node_i]+dof for dof in range(3)] +
                   [3*order[element.node_j]+dof for dof in range(3)])
        state = _element_state(
            element, nodes[element.node_i], nodes[element.node_j],
            [displacement[index] for index in indices])
        element_results.append({
            "element_id": element.id, "node_i": element.node_i,
            "node_j": element.node_j, "length_m": state["length_m"],
            "i": {"N_n": -state["axial_n"], "Vy_n": 0.0,
                  "Vz_n": state["shear_n"], "T_nm": 0.0,
                  "My_nm": state["moment_i_nm"], "Mz_nm": 0.0},
            "j": {"N_n": state["axial_n"], "Vy_n": 0.0,
                  "Vz_n": -state["shear_n"], "T_nm": 0.0,
                  "My_nm": state["moment_j_nm"], "Mz_nm": 0.0},
        })
    cable_results = []
    for cable in model.cables:
        indices = ([3*order[cable.node_i]+dof for dof in range(3)] +
                   [3*order[cable.node_j]+dof for dof in range(3)])
        state = _cable_state(
            cable, nodes[cable.node_i], nodes[cable.node_j],
            [displacement[index] for index in indices])
        cable_results.append({
            "cable_id": cable.id, "node_i": cable.node_i,
            "node_j": cable.node_j, **state,
        })
    return {
        "converged": converged,
        "iterations": iterations,
        "completed_load_factor": completed_factor,
        "load_history": load_history,
        "node_displacements": {
            node.id: displacement[3*order[node.id]:3*order[node.id]+3]
            for node in model.nodes},
        "node_reactions": {
            node.id: [internal[3*order[node.id]+dof]-
                      completed_factor*external[3*order[node.id]+dof]
                      for dof in range(3)]
            for node in model.nodes},
        "element_results": element_results,
        "cable_results": cable_results,
    }
