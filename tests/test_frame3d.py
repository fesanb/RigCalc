import unittest

from rigcalc.solver.frame3d import (FrameElement, FrameModel, FrameNode,
                                    element_axes, global_uniform_load_to_local,
                                    uniform_local_equivalent_load, solve_frame)


class Frame3DTests(unittest.TestCase):
    def test_global_gravity_is_resolved_into_inclined_element_axes(self):
        start = FrameNode("A", 0, 0, 0)
        end = FrameNode("B", 3, 0, 4)
        axes = element_axes(start, end, (0, 0, 1))
        local_load = global_uniform_load_to_local((0, 0, -10), axes)
        self.assertAlmostEqual(local_load[0], -8.0)
        self.assertAlmostEqual(local_load[1], 0.0)
        self.assertAlmostEqual(local_load[2], -6.0)
        local_equivalent = uniform_local_equivalent_load(local_load, 5.0)
        transform = [list(axis) for axis in axes]
        global_force = [sum(transform[column][row] *
                            (local_equivalent[column] +
                             local_equivalent[column+6])
                            for column in range(3))
                        for row in range(3)]
        self.assertAlmostEqual(global_force[0], 0.0)
        self.assertAlmostEqual(global_force[1], 0.0)
        self.assertAlmostEqual(global_force[2], -50.0)

    def test_axial_bar_matches_closed_form_solution(self):
        model = FrameModel(
            nodes=[
                FrameNode("A", 0, 0, 0, restrained=(True,)*6),
                FrameNode(
                    "B", 1, 0, 0,
                    restrained=(False, True, True, True, True, True),
                    load=(1000, 0, 0, 0, 0, 0)),
            ],
            elements=[FrameElement(
                "E", "A", "B", 100.0e9, 40.0e9, 0.01,
                1.0e-6, 1.0e-6, 1.0e-6)],
        )
        result = solve_frame(model)
        self.assertAlmostEqual(result["node_displacements"]["B"][0], 1.0e-6)
        self.assertAlmostEqual(result["node_reactions"]["A"][0], -1000.0)
        forces = result["element_results"][0]["local_end_forces"]
        self.assertEqual(result["element_results"][0]["node_i"], "A")
        self.assertEqual(result["element_results"][0]["node_j"], "B")
        self.assertAlmostEqual(forces[0], -1000.0)
        self.assertAlmostEqual(forces[6], 1000.0)


if __name__ == "__main__":
    unittest.main()
