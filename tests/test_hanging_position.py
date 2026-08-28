import unittest

from rigcalc.vw.hanging_position import extract_hanging_position_trusses


def child(system):
    return {
        "parametric_record": "TrussItem",
        "position": {"x": 0, "y": 0, "z": 1000},
        "orientation": [True, 0, -30, 0, False],
        "parametric_fields": {
            "Name": "Truss", "ItemType": "Line", "Length": "3000",
            "Width": "300", "Height": "300", "TrussSystem": system,
        },
    }


class HangingPositionTests(unittest.TestCase):
    def test_duplicate_internal_representations_are_deduplicated_by_geometry(self):
        inventory = [{
            "scan_id": "P010", "parametric_record": "Light Position Obj",
            "layer_name": "Rigging", "position": {"x": 100, "y": 200, "z": 0},
            "orientation": [True, 0, 0, 90, False],
            "parametric_fields": {"Position Name": "LX Test"},
            "nested_content": [child("T1"), child("T2")],
        }]
        trusses = extract_hanging_position_trusses(inventory, ["Rigging"])
        self.assertEqual(len(trusses), 1)
        truss = trusses[0]
        self.assertAlmostEqual(truss.start.x, 100)
        self.assertAlmostEqual(truss.start.y, 200)
        self.assertAlmostEqual(truss.start.z, 1000)
        self.assertAlmostEqual(truss.geometric_length_mm, 3000)
        self.assertEqual(truss.vw_truss_system, "HP:P010")
        self.assertEqual(truss.source_position_name, "LX Test")

    def test_unselected_hanging_position_is_not_imported(self):
        inventory = [{
            "scan_id": "P010", "parametric_record": "Light Position Obj",
            "layer_name": "Floor", "nested_content": [child("T1")],
        }]
        self.assertEqual(extract_hanging_position_trusses(inventory, ["Rigging"]), [])


if __name__ == "__main__":
    unittest.main()
