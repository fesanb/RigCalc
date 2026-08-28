import unittest

from rigcalc.solver.comparison import (
    compare_calculations, select_primary_calculation)


def reaction(support_id, mass):
    return {"support_id": support_id, "reaction_mass_kg": mass}


class SolverComparisonTests(unittest.TestCase):
    def calculations(self, converged=True):
        linear = {"limitations": [], "unassigned": {}, "constructions": [{
            "construction_id": "C", "status": "preliminary",
            "writeback_eligible": True, "stations": [],
            "reactions": [reaction("A", 10), reaction("B", 20),
                          reaction("C", 30)],
        }]}
        nonlinear = {"constructions": [{
            "construction_id": "C", "status": "diagnostic",
            "converged": converged,
            "validation": {"vertical_equilibrium_ok": converged},
            "issues": [], "stations": [],
            "reactions": [reaction("A", 11), reaction("B", 18),
                          reaction("C", 31)],
        }]}
        return linear, nonlinear

    def test_comparison_reports_reaction_differences(self):
        linear, nonlinear = self.calculations()
        result = compare_calculations(linear, nonlinear)
        self.assertEqual(
            result["constructions"][0]["reactions"][0]["difference_kg"], 1)

    def test_validated_multi_support_nonlinear_result_becomes_primary(self):
        linear, nonlinear = self.calculations()
        selected = select_primary_calculation(linear, nonlinear)
        item = selected["constructions"][0]
        self.assertEqual(item["primary_solver"], "corotational")
        self.assertEqual(item["status"], "preliminary")
        self.assertTrue(item["writeback_eligible"])

    def test_nonconverged_result_falls_back_to_linear(self):
        linear, nonlinear = self.calculations(False)
        item = select_primary_calculation(linear, nonlinear)["constructions"][0]
        self.assertEqual(item["primary_solver"], "linear")


if __name__ == "__main__":
    unittest.main()
