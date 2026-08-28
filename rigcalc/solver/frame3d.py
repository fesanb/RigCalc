"""Linear elastic 3D Euler-Bernoulli frame solver.

Units are N, m, Pa and m^2/m^4. Each node has six global degrees of freedom:
ux, uy, uz, rx, ry, rz. This module contains no Vectorworks dependencies.
"""

from dataclasses import dataclass, field
from math import sqrt

from .linalg import solve_linear_system


DOF_PER_NODE = 6


@dataclass
class FrameNode:
    id: str
    x: float
    y: float
    z: float
    restrained: tuple = (False, False, False, False, False, False)
    load: tuple = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


@dataclass
class FrameElement:
    id: str
    node_i: str
    node_j: str
    elastic_modulus_pa: float
    shear_modulus_pa: float
    area_m2: float
    torsion_constant_m4: float
    iy_m4: float
    iz_m4: float
    reference_vector: tuple = (0.0, 0.0, 1.0)
    uniform_local_load_n_m: tuple = (0.0, 0.0, 0.0)


@dataclass
class FrameModel:
    nodes: list = field(default_factory=list)
    elements: list = field(default_factory=list)


def _zeros(rows, columns):
    return [[0.0 for _ in range(columns)] for _ in range(rows)]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(vector):
    length = sqrt(_dot(vector, vector))
    if length <= 1.0e-12:
        raise ValueError("zero_length_vector")
    return tuple(value / length for value in vector)


def element_axes(node_i, node_j, reference_vector):
    local_x = _unit((node_j.x - node_i.x, node_j.y - node_i.y,
                     node_j.z - node_i.z))
    reference = _unit(reference_vector)
    local_y_seed = _cross(reference, local_x)
    if sqrt(_dot(local_y_seed, local_y_seed)) <= 1.0e-10:
        fallback = (0.0, 1.0, 0.0) if abs(local_x[1]) < 0.9 else (1.0, 0.0, 0.0)
        local_y_seed = _cross(fallback, local_x)
    local_y = _unit(local_y_seed)
    local_z = _unit(_cross(local_x, local_y))
    return local_x, local_y, local_z


def local_stiffness(element, length):
    e, g, a = (element.elastic_modulus_pa, element.shear_modulus_pa,
               element.area_m2)
    j, iy, iz = (element.torsion_constant_m4, element.iy_m4, element.iz_m4)
    k = _zeros(12, 12)

    def place(indices, values):
        for row, global_row in enumerate(indices):
            for column, global_column in enumerate(indices):
                k[global_row][global_column] += values[row][column]

    axial = e * a / length
    place((0, 6), ((axial, -axial), (-axial, axial)))
    torsion = g * j / length
    place((3, 9), ((torsion, -torsion), (-torsion, torsion)))

    bz = e * iz
    place((1, 5, 7, 11), (
        (12*bz/length**3, 6*bz/length**2, -12*bz/length**3, 6*bz/length**2),
        (6*bz/length**2, 4*bz/length, -6*bz/length**2, 2*bz/length),
        (-12*bz/length**3, -6*bz/length**2, 12*bz/length**3, -6*bz/length**2),
        (6*bz/length**2, 2*bz/length, -6*bz/length**2, 4*bz/length)))
    by = e * iy
    place((2, 4, 8, 10), (
        (12*by/length**3, -6*by/length**2, -12*by/length**3, -6*by/length**2),
        (-6*by/length**2, 4*by/length, 6*by/length**2, 2*by/length),
        (-12*by/length**3, 6*by/length**2, 12*by/length**3, 6*by/length**2),
        (-6*by/length**2, 2*by/length, 6*by/length**2, 4*by/length)))
    return k


def transformation_matrix(axes):
    rotation = [list(axis) for axis in axes]
    transform = _zeros(12, 12)
    for block in range(4):
        offset = block * 3
        for row in range(3):
            for column in range(3):
                transform[offset + row][offset + column] = rotation[row][column]
    return transform


def _transpose(matrix):
    return [list(row) for row in zip(*matrix)]


def _matmul(left, right):
    columns = list(zip(*right))
    return [[sum(a*b for a, b in zip(row, column)) for column in columns]
            for row in left]


def _matvec(matrix, vector):
    return [sum(a*b for a, b in zip(row, vector)) for row in matrix]


def uniform_local_equivalent_load(load, length):
    qx, qy, qz = load
    return [
        qx*length/2, qy*length/2, qz*length/2,
        0.0, -qz*length**2/12, qy*length**2/12,
        qx*length/2, qy*length/2, qz*length/2,
        0.0, qz*length**2/12, -qy*length**2/12,
    ]


def solve_frame(model):
    nodes = {node.id: node for node in model.nodes}
    order = {node.id: index for index, node in enumerate(model.nodes)}
    size = len(model.nodes) * DOF_PER_NODE
    stiffness, loads = _zeros(size, size), [0.0] * size
    element_data = {}
    for node in model.nodes:
        start = order[node.id] * DOF_PER_NODE
        for dof, value in enumerate(node.load):
            loads[start + dof] += value
    for element in model.elements:
        node_i, node_j = nodes[element.node_i], nodes[element.node_j]
        axes = element_axes(node_i, node_j, element.reference_vector)
        length = sqrt((node_j.x-node_i.x)**2 + (node_j.y-node_i.y)**2 +
                      (node_j.z-node_i.z)**2)
        local_k = local_stiffness(element, length)
        transform = transformation_matrix(axes)
        global_k = _matmul(_transpose(transform), _matmul(local_k, transform))
        local_f = uniform_local_equivalent_load(
            element.uniform_local_load_n_m, length)
        global_f = _matvec(_transpose(transform), local_f)
        indices = ([order[element.node_i]*6 + dof for dof in range(6)] +
                   [order[element.node_j]*6 + dof for dof in range(6)])
        for row, global_row in enumerate(indices):
            loads[global_row] += global_f[row]
            for column, global_column in enumerate(indices):
                stiffness[global_row][global_column] += global_k[row][column]
        element_data[element.id] = (
            element, indices, transform, local_k, local_f, length)
    restrained = []
    for node in model.nodes:
        base = order[node.id] * 6
        restrained.extend(base+dof for dof, fixed in enumerate(node.restrained)
                           if fixed)
    free = [index for index in range(size) if index not in set(restrained)]
    reduced_k = [[stiffness[row][column] for column in free] for row in free]
    reduced_f = [loads[row] for row in free]
    reduced_u = solve_linear_system(reduced_k, reduced_f) if free else []
    # Iterative refinement reduces round-off residuals in long beams where
    # translational and rotational stiffness terms differ by many orders.
    for _ in range(3):
        equation_residual = [
            applied-calculated for applied, calculated in
            zip(reduced_f, _matvec(reduced_k, reduced_u))]
        reference = max([abs(value) for value in reduced_f] + [1.0])
        if max([abs(value) for value in equation_residual] + [0.0]) <= 1.0e-11*reference:
            break
        correction = solve_linear_system(reduced_k, equation_residual)
        reduced_u = [value+delta for value, delta in zip(reduced_u, correction)]
    displacement = [0.0] * size
    for index, value in zip(free, reduced_u):
        displacement[index] = value
    residual = [value - applied for value, applied in
                zip(_matvec(stiffness, displacement), loads)]
    element_results = []
    for element_id, data in element_data.items():
        element, indices, transform, local_k, local_f, length = data
        local_u = _matvec(transform, [displacement[index] for index in indices])
        local_end_forces = [value-applied for value, applied in
                            zip(_matvec(local_k, local_u), local_f)]
        element_results.append({
            "element_id": element_id, "node_i": element.node_i,
            "node_j": element.node_j, "length_m": length,
            "local_end_forces": local_end_forces,
        })
    return {
        "node_displacements": {
            node.id: displacement[order[node.id]*6:order[node.id]*6+6]
            for node in model.nodes},
        "node_reactions": {
            node.id: residual[order[node.id]*6:order[node.id]*6+6]
            for node in model.nodes},
        "element_results": element_results,
    }
