import unittest

from rigcalc.model import DocumentModel, Point3D, PointLoad
from rigcalc.vw.scanner import (_parse_lighting_pipe, _parse_load,
                                _parse_support, _suppress_speaker_array_members)


class FakeVS:
    def GetSymLoc(self, handle): return 100.0, 200.0
    def Get3DCntr(self, handle): return 0.0, 1800.0


class ScannerDeduplicationTests(unittest.TestCase):
    def test_lighting_pipe_becomes_geometric_carrier_with_self_weight(self):
        pipe = _parse_lighting_pipe(FakeVS(), "handle", "P1", {
            "Index": "T1", "TotalLength": "3000", "Weight": "12126.8",
            "pipeW": "48",
        })
        self.assertEqual(pipe.item_type, "Lighting Pipe")
        self.assertTrue(pipe.is_line)
        self.assertAlmostEqual(pipe.end.x, 3100.0)
        self.assertAlmostEqual(pipe.position.z, 1800.0)
        self.assertAlmostEqual(pipe.self_weight_kg, 12.1268)

    def test_inverted_hoist_uses_load_trim_as_lower_connection(self):
        support = _parse_support(FakeVS(), "handle", "H1", {
            "HoistPos": "Hoist Up", "OriginX": "100", "OriginY": "200",
            "LoadTrim": "5542", "TrussBottomTrim": "0",
        })
        self.assertAlmostEqual(support.position.z, 5542.0)

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
