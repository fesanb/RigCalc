"""Independent Euler-Bernoulli reference used only by solver tests.

This deliberately uses two DOF per node and does not import RigCalc's frame
assembly, transformation, or linear-algebra modules.
"""


def _solve(matrix, vector):
    matrix = [list(row) for row in matrix]
    vector = list(vector)
    for column in range(len(vector)):
        pivot = max(range(column, len(vector)),
                    key=lambda row: abs(matrix[row][column]))
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        vector[column], vector[pivot] = vector[pivot], vector[column]
        for row in range(column+1, len(vector)):
            factor = matrix[row][column]/matrix[column][column]
            for entry in range(column, len(vector)):
                matrix[row][entry] -= factor*matrix[column][entry]
            vector[row] -= factor*vector[column]
    result = [0.0]*len(vector)
    for row in range(len(vector)-1, -1, -1):
        result[row] = (vector[row]-sum(
            matrix[row][column]*result[column]
            for column in range(row+1, len(vector))))/matrix[row][row]
    return result


def solve_uniform_beam(stations_m, support_indices, ei_by_span, load_n_m):
    size = 2*len(stations_m)
    stiffness = [[0.0]*size for _ in range(size)]
    loads = [0.0]*size
    for span, (start, end) in enumerate(zip(stations_m, stations_m[1:])):
        length = end-start
        factor = ei_by_span[span]/length**3
        local = [[12, 6*length, -12, 6*length],
                 [6*length, 4*length**2, -6*length, 2*length**2],
                 [-12, -6*length, 12, -6*length],
                 [6*length, 2*length**2, -6*length, 4*length**2]]
        equivalent = [-load_n_m*length/2, -load_n_m*length**2/12,
                      -load_n_m*length/2, load_n_m*length**2/12]
        indices = [2*span, 2*span+1, 2*span+2, 2*span+3]
        for row, global_row in enumerate(indices):
            loads[global_row] += equivalent[row]
            for column, global_column in enumerate(indices):
                stiffness[global_row][global_column] += factor*local[row][column]
    restrained = {2*index for index in support_indices}
    free = [index for index in range(size) if index not in restrained]
    reduced = [[stiffness[row][column] for column in free] for row in free]
    displacement = [0.0]*size
    for index, value in zip(free, _solve(reduced, [loads[row] for row in free])):
        displacement[index] = value
    residual = [sum(stiffness[row][column]*displacement[column]
                    for column in range(size))-loads[row]
                for row in range(size)]
    return [residual[2*index] for index in support_indices]
