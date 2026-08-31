import unittest

from rigcalc.model import DocumentModel, Point3D, Support
from rigcalc.notifications import evaluate_zero_hoist_outcomes
from rigcalc.report.hoist_outcomes import (build_hoist_outcomes,
                                           make_hoist_outcomes_text)


class HoistOutcomeTests(unittest.TestCase):
    def test_unassigned_hoist_gets_zero_outcome_reason_and_marker(self):
        hoist = Support("H1", "Hoist", Point3D(1, 2), hoist_id="M01")
        document = DocumentModel(
            supports=[hoist], unassigned_supports=[hoist],
            unassigned_support_diagnostics={"H1": {
                "reason": "no_safe_geometry_attachment"}})
        outcomes = build_hoist_outcomes(document, {"constructions": []})
        self.assertEqual(outcomes[0]["status"], "zero_not_calculated")
        self.assertEqual(outcomes[0]["reaction_mass_kg"], 0.0)
        self.assertEqual(outcomes[0]["reason"], "no_safe_geometry_attachment")
        self.assertFalse(outcomes[0]["writeback_eligible"])
        self.assertIn("0.00 kN", make_hoist_outcomes_text(outcomes))
        self.assertEqual(evaluate_zero_hoist_outcomes(outcomes)[0]["support_id"],
                         "H1")

    def test_ineligible_calculation_remains_diagnostic_not_zeroed(self):
        hoist = Support("H1", "Hoist", Point3D(1, 2), hoist_id="M01")
        document = DocumentModel(supports=[hoist])
        calculation = {"constructions": [{
            "construction_id": "C1", "status": "diagnostic",
            "writeback_eligible": False,
            "issues": ["inclined_geometry_diagnostic_not_writeback_source"],
            "reactions": [{"support_id": "H1", "support_kind": "hoist",
                           "is_structural_link": False,
                           "reaction_mass_kg": 100.0,
                           "preliminary_high_hook_mass_kg": 110.0}],
        }]}
        outcome = build_hoist_outcomes(document, calculation)[0]
        self.assertEqual(outcome["status"], "diagnostic_only")
        self.assertAlmostEqual(outcome["reaction_mass_kg"], 100.0)
        self.assertEqual(evaluate_zero_hoist_outcomes([outcome]), [])


if __name__ == "__main__":
    unittest.main()
