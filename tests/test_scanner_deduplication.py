import unittest

from rigcalc.model import DocumentModel, Point3D, PointLoad
from rigcalc.vw.scanner import _suppress_speaker_array_members


class ScannerDeduplicationTests(unittest.TestCase):
    def test_speaker_included_in_nearby_array_is_suppressed(self):
        speaker = PointLoad(
            "S1", "", Point3D(0, 0, 0), "Speaker", weight_kg=20)
        array = PointLoad(
            "A1", "", Point3D(20, 10, 200), "Speaker Array", weight_kg=27)
        document = DocumentModel(point_loads=[speaker, array])

        _suppress_speaker_array_members(document)

        self.assertEqual([item.id for item in document.point_loads], ["A1"])
        self.assertEqual([item.id for item in document.suppressed_point_loads], ["S1"])


if __name__ == "__main__":
    unittest.main()
