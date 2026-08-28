import json
import os
import tempfile
import unittest

from rigcalc.model import DocumentModel, Point3D, Support
from rigcalc.report.json_report import write_json_report


class UncopyableHandle:
    def __deepcopy__(self, memo):
        raise TypeError("opaque handle must not be copied")


class JsonReportTests(unittest.TestCase):
    def test_opaque_source_reference_is_excluded_without_copying(self):
        document = DocumentModel(supports=[
            Support("H1", "Hoist", Point3D(0, 0), source_ref=UncopyableHandle())
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.json")
            write_json_report(path, document, [], {})
            with open(path, encoding="utf-8") as stream:
                data = json.load(stream)
        self.assertNotIn("source_ref", data["document"]["supports"][0])

    def test_support_geometry_evidence_is_preserved(self):
        document = DocumentModel(supports=[Support(
            "H1", "Hoist", Point3D(10, 20, 30),
            object_position=Point3D(10, 20, 130),
            geometry_fields={"HoistPos": "Hoist Up", "LoHook": "30"},
        )])
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.json")
            write_json_report(path, document, [], {})
            with open(path, encoding="utf-8") as stream:
                support = json.load(stream)["document"]["supports"][0]
        self.assertEqual(support["geometry_fields"]["HoistPos"], "Hoist Up")
        self.assertEqual(support["object_position"]["z"], 130)


if __name__ == "__main__":
    unittest.main()
