"""Sparse symmetric positive-definite solver for frame stiffness systems.

Pure Python, no dependencies.  Degrees of freedom are reordered with reverse
Cuthill-McKee to keep the envelope (skyline) narrow, then factorised with an
envelope Cholesky decomposition.  A non-positive pivot means the structure is
a mechanism (or numerically indistinguishable from one) and is reported as
``singular_stiffness_matrix`` rather than producing a meaningless result.
"""

from collections import deque
from math import sqrt


class SparseSymmetric:
    """Symmetric matrix stored as a dict of row dicts (both triangles)."""

    def __init__(self, size):
        self.size = size
        self.rows = [dict() for _ in range(size)]

    def add(self, row, column, value):
        if value == 0.0:
            return
        self.rows[row][column] = self.rows[row].get(column, 0.0)+value
        if row != column:
            self.rows[column][row] = self.rows[column].get(row, 0.0)+value

    def add_symmetric_block(self, indices, block):
        """Add a full symmetric block; only the upper triangle is read."""
        for a, row in enumerate(indices):
            if row is None:
                continue
            for b in range(a, len(indices)):
                column = indices[b]
                if column is None:
                    continue
                value = block[a][b]
                if value == 0.0:
                    continue
                if row == column:
                    self.rows[row][row] = self.rows[row].get(row, 0.0)+value
                else:
                    self.rows[row][column] = (
                        self.rows[row].get(column, 0.0)+value)
                    self.rows[column][row] = (
                        self.rows[column].get(row, 0.0)+value)

    def multiply(self, vector):
        return [sum(value*vector[column] for column, value in row.items())
                for row in self.rows]


def reverse_cuthill_mckee(matrix):
    size = matrix.size
    degree = [len(row) for row in matrix.rows]
    visited = [False]*size
    order = []
    for seed in sorted(range(size), key=lambda index: degree[index]):
        if visited[seed]:
            continue
        visited[seed] = True
        queue = deque([seed])
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbour in sorted(
                    (item for item in matrix.rows[node] if not visited[item]),
                    key=lambda index: degree[index]):
                visited[neighbour] = True
                queue.append(neighbour)
    order.reverse()
    return order


def solve_spd(matrix, vector, pivot_tolerance=1.0e-12):
    """Solve K x = f; return (x, diagnostics).  Raises on a mechanism."""
    size = matrix.size
    if size == 0:
        return [], {"method": "envelope_cholesky_rcm", "pivot_count": 0,
                    "minimum_scaled_pivot": 0.0, "maximum_scaled_pivot": 0.0}
    order = reverse_cuthill_mckee(matrix)
    position = [0]*size
    for new, old in enumerate(order):
        position[old] = new
    rows = [dict() for _ in range(size)]
    for old_row, entries in enumerate(matrix.rows):
        new_row = position[old_row]
        for old_column, value in entries.items():
            new_column = position[old_column]
            if new_column <= new_row:
                rows[new_row][new_column] = value
    first = [min(row) if row else index for index, row in enumerate(rows)]
    # Envelope storage: lower[i][k - first[i]] holds L[i][k].
    lower = []
    scaled = []
    for i in range(size):
        start = first[i]
        row = [rows[i].get(k, 0.0) for k in range(start, i+1)]
        for j in range(start, i):
            start_j = first[j]
            k0 = max(start, start_j)
            total = row[j-start]
            lower_j = lower[j]
            for k in range(k0, j):
                total -= row[k-start]*lower_j[k-start_j]
            row[j-start] = total/lower_j[j-start_j]
        diagonal = row[i-start]
        for k in range(start, i):
            diagonal -= row[k-start]*row[k-start]
        reference = abs(rows[i].get(i, 0.0)) or 1.0
        if diagonal <= pivot_tolerance*reference:
            raise ValueError("singular_stiffness_matrix")
        scaled.append(diagonal/reference)
        row[i-start] = sqrt(diagonal)
        lower.append(row)
    def substitute(values):
        permuted = [0.0]*size
        for old, value in enumerate(values):
            permuted[position[old]] = value
        forward = [0.0]*size
        for i in range(size):
            start = first[i]
            row = lower[i]
            total = permuted[i]
            for k in range(start, i):
                total -= row[k-start]*forward[k]
            forward[i] = total/row[i-start]
        solution = forward[:]
        for i in range(size-1, -1, -1):
            start = first[i]
            row = lower[i]
            solution[i] /= row[i-start]
            value = solution[i]
            for k in range(start, i):
                solution[k] -= row[k-start]*value
        return [solution[position[old]] for old in range(size)]

    result = substitute(vector)
    # Iterative refinement with the same factor: stiff truss chords next to
    # weak stabilising springs span many orders of magnitude.
    refinements = 0
    scale = max([abs(value) for value in vector]+[1.0])
    for _ in range(3):
        residual = [b-a for a, b in zip(matrix.multiply(result), vector)]
        if max([abs(value) for value in residual]+[0.0]) <= 1.0e-13*scale:
            break
        correction = substitute(residual)
        result = [a+b for a, b in zip(result, correction)]
        refinements += 1
    bandwidth = max((i-first[i] for i in range(size)), default=0)
    return result, {
        "method": "envelope_cholesky_rcm",
        "pivot_count": size,
        "minimum_scaled_pivot": min(scaled),
        "maximum_scaled_pivot": max(scaled),
        "maximum_bandwidth": bandwidth,
        "iterative_refinement_steps": refinements,
    }
