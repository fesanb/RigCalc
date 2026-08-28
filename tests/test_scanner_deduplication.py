import unittest

from rigcalc.model import DocumentModel, Point3D, PointLoad
from rigcalc.vw.scanner import _parse_load, _suppress_speaker_array_members


class FakeVS:
    def GetSymLoc(self, handle): return 100.0, 200.0
    def Get3DCntr(self, handle): return 0.0, 1800.0


class ScannerDeduplicationTests(unittest.TestCase):
    def test_soft_goods_attaches_at_top_trim_not_geometry_centre(self):
        item = _parse_load(FakeVS(), "handle", "L1", "Soft Goods", {
            "TopTrim": "4959,36", "Z Location": "1815,86",
            "WeightKG": "45,37",
        })
        self.assertAlmostEqual(item.position.z, 4959.36)

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
