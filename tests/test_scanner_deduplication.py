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

    def test_hoist_down_uses_load_trim_not_stale_bottom_trim(self):
        # An unlinked hoist keeps a stale TrussBottomTrim (0) after the rig
        # is raised; LoadTrim follows the hoist (test drawing regression).
        support = _parse_support(FakeVS(), "handle", "H1", {
            "HoistPos": "Hoist Down", "OriginX": "100", "OriginY": "200",
            "LoadTrim": "8,454993582983418e03", "LoHook": "8454,99",
            "TrussBottomTrim": "0e00",
        })
        self.assertAlmostEqual(support.position.z, 8454.993582983418)
        self.assertEqual(
            support.geometry_fields["RigCalcLowerConnectionSource"],
            "LoadTrim")

    def test_zero_trim_is_a_real_elevation_not_missing(self):
        support = _parse_support(FakeVS(), "handle", "H1", {
            "HoistPos": "Hoist Down", "OriginX": "100", "OriginY": "200",
            "LoadTrim": "0e00",
        })
        self.assertAlmostEqual(support.position.z, 0.0)

    def test_bottom_trim_is_used_when_load_trim_is_missing(self):
        support = _parse_support(FakeVS(), "handle", "H1", {
            "HoistPos": "Hoist Down", "OriginX": "100", "OriginY": "200",
            "TrussBottomTrim": "0",
        })
        self.assertAlmostEqual(support.position.z, 0.0)
        self.assertEqual(
            support.geometry_fields["RigCalcLowerConnectionSource"],
            "TrussBottomTrim")

    def test_deadhang_symbol_placeholder_capacity_is_ignored(self):
        support = _parse_support(FakeVS(), "handle", "H1", {
            "HoistPos": "Hoist Down", "OriginX": "100", "OriginY": "200",
            "TrussBottomTrim": "0", "SymbolUsed": "DeadHang",
            "Capacity": "1",
        })
        self.assertEqual(support.capacity_kg, 0.0)

    def test_zero_load_trim_is_used_for_inverted_hoist(self):
        support = _parse_support(FakeVS(), "handle", "H1", {
            "HoistPos": "Hoist Up", "OriginX": "100", "OriginY": "200",
            "LoadTrim": "0", "TrussBottomTrim": "-143,5",
        })
        self.assertAlmostEqual(support.position.z, 0.0)
        self.assertEqual(
            support.geometry_fields["RigCalcLowerConnectionSource"],
            "LoadTrim")

    def test_missing_trims_fall_back_to_geometry_centre_explicitly(self):
        support = _parse_support(FakeVS(), "handle", "H1", {
            "HoistPos": "Hoist Down", "OriginX": "100", "OriginY": "200",
        })
        self.assertAlmostEqual(support.position.z, 1800.0)
        self.assertEqual(
            support.geometry_fields["RigCalcLowerConnectionSource"],
            "geometry_centre_fallback")

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
