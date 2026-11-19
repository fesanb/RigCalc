import unittest

from rigcalc.model import (AttachedObject, Attachment, Construction,
                           DocumentModel, Point3D, PointLoad, Support)
from rigcalc.notifications import evaluate_zero_hoist_outcomes
from rigcalc.report.hoist_outcomes import (build_hoist_outcomes,
                                           make_hoist_outcomes_text)


class HoistOutcomeTests(unittest.TestCase):
    def test_unconnected_hoist_is_exempt_without_a_red_marker(self):
        hoist = Support("H1", "Hoist", Point3D(1, 2), hoist_id="M01")
        document = DocumentModel(
            supports=[hoist], unassigned_supports=[hoist],
            unassigned_support_diagnostics={"H1": {
                "reason": "no_safe_geometry_attachment"}})
        outcomes = build_hoist_outcomes(document, {"constructions": []})
        self.assertEqual(outcomes[0]["status"], "exempt_not_connected")
        self.assertEqual(outcomes[0]["reaction_mass_kg"], 0.0)
        self.assertEqual(outcomes[0]["reason"], "exempt_not_connected")
        self.assertFalse(outcomes[0]["writeback_eligible"])
        self.assertEqual(evaluate_zero_hoist_outcomes(outcomes), [])

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

    def test_attached_unsolved_hoist_reports_solver_reason_and_evidence(self):
        hoist = Support("H1", "Hoist", Point3D(1, 2), hoist_id="M01")
        attached = AttachedObject(hoist, Attachment(
            "T1", "Truss", 12.0, 100.0, 100.0, 1.0, 2.0,
            method="geometry_3d_support", confidence="INFERRED",
            carrier_clearance_mm=4.0))
        construction = Construction("C1", [], [], "branched",
                                    supports=[attached])
        outcome = build_hoist_outcomes(
            DocumentModel(supports=[hoist]), {"constructions": [{
                "construction_id": "C1", "status": "not_calculated",
                "issues": ["requires_branched_or_loop_solver"],
                "reactions": [],
            }]}, topology_constructions=[construction])[0]
        self.assertEqual(outcome["status"], "zero_not_calculated")
        self.assertEqual(outcome["reason"], "requires_branched_or_loop_solver")
        self.assertEqual(outcome["association_evidence"]["truss_id"], "T1")

    def test_free_hoist_uses_manual_load_without_writeback(self):
        hoist = Support("H1", "Hoist", Point3D(1, 2), hoist_id="M01",
                        manual_load_kg=200.0, weight_with_chain_kg=17.32)
        outcome = build_hoist_outcomes(
            DocumentModel(supports=[hoist], unassigned_supports=[hoist],
                          unassigned_support_diagnostics={"H1": {}}),
            {"constructions": []})[0]
        self.assertEqual(outcome["status"], "manual_direct_load")
        self.assertAlmostEqual(outcome["high_hook_mass_kg"], 217.32)
        self.assertFalse(outcome["writeback_eligible"])

    def test_free_hoist_keeps_unfactored_direct_load_visible(self):
        hoist = Support("H1", "Hoist", Point3D(0, 0), hoist_id="M01",
                        weight_with_chain_kg=20.0,
                        weight_with_chain_raw_kg=17.32)
        load = PointLoad("L1", "Load", Point3D(0, 0), "Lighting Device",
                         weight_kg=240.0, unfactored_weight_kg=200.0)
        outcome = build_hoist_outcomes(
            DocumentModel(supports=[hoist], unassigned_point_loads=[load]),
            {"constructions": []})[0]
        self.assertEqual(outcome["reaction_mass_kg"], 200.0)
        self.assertAlmostEqual(outcome["high_hook_mass_kg"], 217.32)

    def test_unconnected_hoist_is_exempt_not_a_zero_error(self):
        hoist = Support("H1", "Hoist", Point3D(1, 2), hoist_id="M01")
        outcome = build_hoist_outcomes(
            DocumentModel(supports=[hoist], unassigned_supports=[hoist],
                          unassigned_support_diagnostics={"H1": {}}),
            {"constructions": []})[0]
        self.assertEqual(outcome["status"], "exempt_not_connected")
        self.assertEqual(evaluate_zero_hoist_outcomes([outcome]), [])


if __name__ == "__main__":
    unittest.main()
