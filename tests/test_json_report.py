import json
import os
import tempfile
import unittest

from loadcalc.model import DocumentModel, Point3D, Support
from loadcalc.report.json_report import write_json_report


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


if __name__ == "__main__":
    unittest.main()
