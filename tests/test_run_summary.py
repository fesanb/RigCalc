import unittest

from rigcalc.model import DocumentModel, Point3D, PointLoad
from rigcalc.report.run_summary import build_run_summary, make_run_summary_text


class RunSummaryTests(unittest.TestCase):
    def test_counts_errors_unhandled_and_irrelevant_objects_separately(self):
        document = DocumentModel(
            unassigned_point_loads=[
                PointLoad("L", "", Point3D(0, 0), "Load")],
            ignored_record_types=["Data Tag", "Light Position Obj"])
        primary = {"constructions": [{
            "construction_id": "C1", "status": "preliminary",
            "writeback_eligible": True, "primary_solver": "linear",
            "released_support_count": 2,
        }]}
        written = {"items": [{"status": "written"}]}
        summary = build_run_summary(
            document, [object()], primary, written, written)
        self.assertEqual(summary["technical_errors"]["count"], 0)
        self.assertEqual(
            summary["unhandled_calculation_objects"]["count"], 1)
        self.assertEqual(
            summary["ignored_irrelevant_plugin_objects"]["count"], 1)
        text = make_run_summary_text(summary)
        self.assertIn("Technical errors: 0", text)
        self.assertIn("Unhandled calculation objects: 1", text)
        self.assertIn("Status: REVIEW REQUIRED", text)

    def test_counts_explicit_hoist_outcomes(self):
        summary = build_run_summary(
            DocumentModel(), [], {"constructions": []},
            {"items": []}, {"items": []}, hoist_outcomes=[
                {"status": "calculated"},
                {"status": "diagnostic_only"},
                {"status": "zero_not_calculated"},
            ])
        self.assertEqual(summary["hoist_outcomes"]["calculated"], 1)
        self.assertEqual(summary["hoist_outcomes"]["diagnostic_only"], 1)
        self.assertEqual(summary["hoist_outcomes"]["zero_not_calculated"], 1)
        self.assertIn("Hoist outcomes — calculated: 1, diagnostic: 1, zero: 1",
                      make_run_summary_text(summary))

    def test_counts_inclined_diagnostic_results_separately(self):
        primary = {"constructions": [{
            "construction_id": "C1", "status": "diagnostic",
            "method": "inclined_planar_3d_frame_diagnostic",
        }]}
        summary = build_run_summary(
            DocumentModel(), [object()], primary, {"items": []}, {"items": []})
        self.assertEqual(summary["diagnostic"]["constructions"], 1)
        self.assertEqual(summary["diagnostic"]["inclined_planar_frames"], 1)
        self.assertEqual(summary["uncalculated_constructions"]["count"], 0)

    def test_invalid_writeback_skip_is_a_visible_technical_error(self):
        skipped = {"items": [{
            "status": "skipped_invalid_high_hook_mass"}]}
        summary = build_run_summary(
            DocumentModel(), [], {"constructions": []}, skipped,
            {"items": []})
        self.assertEqual(summary["technical_errors"]["count"], 1)
        self.assertIn("Status: REVIEW REQUIRED", make_run_summary_text(summary))


if __name__ == "__main__":
    unittest.main()
