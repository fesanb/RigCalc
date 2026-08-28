import unittest

from rigcalc.solver.frame3d import (FrameElement, FrameModel, FrameNode,
                                    solve_frame)


class Frame3DTests(unittest.TestCase):
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
