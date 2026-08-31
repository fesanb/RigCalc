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
            "validation": {
                "vertical_equilibrium_ok": converged,
                "numerically_valid": converged,
                "load_model_valid": converged,
            },
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

    def test_only_a_support_validated_nonlinear_result_becomes_primary(self):
        linear, nonlinear = self.calculations()
        nonlinear["constructions"][0]["writeback_eligible"] = True
        nonlinear["constructions"][0]["validation"]["support_model_valid"] = True
        selected = select_primary_calculation(linear, nonlinear)
        item = selected["constructions"][0]
        self.assertEqual(item["primary_solver"], "corotational")
        self.assertEqual(item["status"], "preliminary")
        self.assertTrue(item["writeback_eligible"])

    def test_diagnostic_nonlinear_result_falls_back_to_linear(self):
        linear, nonlinear = self.calculations()
        item = select_primary_calculation(linear, nonlinear)["constructions"][0]
        self.assertEqual(item["primary_solver"], "linear")

    def test_nonconverged_result_falls_back_to_linear(self):
        linear, nonlinear = self.calculations(False)
        item = select_primary_calculation(linear, nonlinear)["constructions"][0]
        self.assertEqual(item["primary_solver"], "linear")

    def test_missing_explicit_numerical_or_load_validation_falls_back(self):
        for key in ("numerically_valid", "load_model_valid"):
            linear, nonlinear = self.calculations()
            nonlinear["constructions"][0]["writeback_eligible"] = True
            nonlinear["constructions"][0]["validation"]["support_model_valid"] = True
            del nonlinear["constructions"][0]["validation"][key]
            item = select_primary_calculation(
                linear, nonlinear)["constructions"][0]
            self.assertEqual(item["primary_solver"], "linear")


if __name__ == "__main__":
    unittest.main()
