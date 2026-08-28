import unittest

from rigcalc.vw.scanner import _parse_dead_hang


class FakeVS:
    def GetSymLoc(self, _handle):
        return 9591.0, -18656.0

    def Get3DCntr(self, _handle):
        return (0.0, 2516.0)


class DeadHangTests(unittest.TestCase):
    def test_verified_drop_fields_create_structural_support_link(self):
        support = _parse_dead_hang(FakeVS(), "handle", "D193", {
            "Name": "Bridle",
            "AsDrop": "True",
            "BridleType": "DeadHang",
            "RelativeDimX": "9591,0",
            "RelativeDimY": "-18656,0",
            "ApexHeight": "2191,606",
            "DropLength": "2232,246",
            "TrimmLeg1": "4959,360",
            "HouseRiggingPoint1": "upper-port",
            "TotalWeight": "6550",
            "ForceDownLegMax": "9806,65",
        })
        self.assertEqual(support.support_kind, "dead_hang")
        self.assertTrue(support.is_structural_link)
        self.assertAlmostEqual(support.position.z, -40.64, places=3)
        self.assertAlmostEqual(support.transfer_target_position.z, 4959.36)
        self.assertAlmostEqual(support.weight_with_chain_kg, 6.55)
        self.assertAlmostEqual(support.capacity_kg, 1000.0)
        self.assertEqual(support.vw_truss_system_top, "upper-port")

    def test_non_drop_bridle_is_not_assumed_to_be_dead_hang_support(self):
        support = _parse_dead_hang(FakeVS(), "handle", "D194", {
            "AsDrop": "False", "BridleType": "Bridle",
            "HouseRiggingPoint1": "upper-port",
        })
        self.assertIsNone(support)


if __name__ == "__main__":
    unittest.main()
