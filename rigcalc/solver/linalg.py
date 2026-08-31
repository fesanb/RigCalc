"""Small dependency-free linear algebra routines used by solver modules."""


def solve_linear_system(matrix, vector, tolerance=1.0e-12,
                        return_diagnostics=False):
    """Solve Ax=b using scaled pivoting, optionally exposing pivot quality."""
    size = len(vector)
    augmented = [list(matrix[row]) + [float(vector[row])]
                 for row in range(size)]
    scales = [max((abs(value) for value in row), default=0.0)
              for row in matrix]
    scaled_pivots = []
    for column in range(size):
        pivot = max(range(column, size),
                    key=lambda row: (abs(augmented[row][column]) / scales[row]
                                     if scales[row] else 0.0))
        if (scales[pivot] == 0.0 or
                abs(augmented[pivot][column]) <= tolerance * scales[pivot]):
            raise ValueError("singular_stiffness_matrix")
        scaled_pivots.append(
            abs(augmented[pivot][column]) / scales[pivot])
        augmented[column], augmented[pivot] = (
            augmented[pivot], augmented[column])
        scales[column], scales[pivot] = scales[pivot], scales[column]
        for row in range(column + 1, size):
            factor = augmented[row][column] / augmented[column][column]
            augmented[row][column] = 0.0
            for entry in range(column + 1, size + 1):
                augmented[row][entry] -= factor * augmented[column][entry]
    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        remainder = sum(augmented[row][column] * solution[column]
                        for column in range(row + 1, size))
        solution[row] = ((augmented[row][size] - remainder) /
                         augmented[row][row])
    if not return_diagnostics:
        return solution
    return solution, {
        "method": "scaled_partial_pivoting",
        "tolerance": tolerance,
        "minimum_scaled_pivot": min(scaled_pivots, default=0.0),
        "maximum_scaled_pivot": max(scaled_pivots, default=0.0),
        "pivot_count": len(scaled_pivots),
    }
