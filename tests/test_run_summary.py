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


if __name__ == "__main__":
    unittest.main()
