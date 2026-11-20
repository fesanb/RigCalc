"""Bridle leg forces against Vectorworks/Braceworks (test drawing, B1).

Field values are copied from the Vectorworks 2027 test drawing.  Vectorworks
reports ForceLeg1/2 = 514.0 / 561.6 N for an apex load of hoist M108's High
Hook (85.91 kg, unfactored, cable 3 kg/m) plus the bridle's 21.42 kg.
"""

import unittest

from rigcalc.model import DocumentModel, Point3D, Support
from rigcalc.notifications import evaluate_bridles
from rigcalc.solver.bridle import calculate_bridles, make_bridle_text
from rigcalc.vw.scanner import _parse_bridle, _parse_house_rigging_point

B1_FIELDS = {
    "Name": "Bridle", "Index": "B1", "TotalWeight": "21420",
    "BridleType": "TwoWay", "ApexHeight": "1,588324358298342e04",
    "DropLength": "0e00",
    "RelativeDimX": "1,114043692816123e04",
    "RelativeDimY": "-1,688079312963585e04",
    "ForceLeg1": "514,00259457", "ForceLeg2": "561,6187283",
    "ForceMaxLeg1": "7000", "ForceMaxLeg2": "9810",
    "LengthLeg1": "7,604079582165438e03",
    "LengthLeg2": "7,574535256434629e03",
    "AngleLeg1": "77,65°", "AngleLeg2": "78,72°",
    "TrimmLeg1": "2,331149358298342e04", "TrimmLeg2": "2,331149358298342e04",
    "ConnectedHoistUUID": "97532407-7e87-45ba-ada6-6ed8eb0f22df",
    "ForceDownLegMax": "14709,97",
}
HOUSE_POINTS = [(10680.0, -18440.0), (11560.0, -15460.0),
                (14960.0, -13320.0), (16560.0, -19640.0)]


class FakeVS:
    def __init__(self, insertion, center):
        self.insertion, self.center = insertion, center

    def GetSymLoc(self, handle):
        return self.insertion

    def Get3DCntr(self, handle):
        return (self.center[0], self.center[1]), self.center[2]

    def GetObjectUuid(self, handle):
        return ""


def document():
    bridle = _parse_bridle(FakeVS((11140.0, -16881.0),
                                  (11120.0, -16950.0, 19597.0)),
                           None, "B1", B1_FIELDS)
    points = [_parse_house_rigging_point(
        FakeVS(point, (point[0], point[1], 23336.0)), None,
        "R{}".format(index), {"OriginX": str(point[0]),
                              "OriginY": str(point[1])})
        for index, point in enumerate(HOUSE_POINTS)]
    hoist = Support("H368", "", Point3D(11140, -16881, 8455),
                    hoist_id="M108",
                    object_uuid="97532407-7e87-45ba-ada6-6ed8eb0f22df")
    return DocumentModel(supports=[hoist], bridles=[bridle],
                         house_rigging_points=points)


def outcome(status="calculated", high_hook=85.91):
    return [{"support_id": "H368", "status": status,
             "high_hook_mass_kg": high_hook}]


class BridleTests(unittest.TestCase):
    def test_parse_reads_units_and_legs(self):
        bridle = document().bridles[0]
        self.assertEqual(len(bridle.legs), 2)
        self.assertAlmostEqual(bridle.weight_raw_kg, 21.42)
        self.assertAlmostEqual(bridle.apex.z, 15883.24, places=1)
        self.assertAlmostEqual(bridle.legs[0].vw_force_n, 514.0026, places=3)

    def test_leg_forces_match_vectorworks(self):
        result = calculate_bridles(document(), outcome())[0]
        self.assertEqual(result["status"], "calculated", result["issues"])
        legs = {item["leg"]: item for item in result["legs"]}
        self.assertEqual(legs[1]["house_rigging_point"], "R0")
        self.assertEqual(legs[2]["house_rigging_point"], "R1")
        self.assertAlmostEqual(legs[1]["force_n"], 514.0, delta=1.0)
        self.assertAlmostEqual(legs[2]["force_n"], 561.6, delta=1.0)
        # The anchor force equals the Vectorworks HouseRiggingPoint force.
        self.assertAlmostEqual(legs[1]["anchor_force_n"][2], -502.1, delta=1.0)
        self.assertIn("Leg 1 -> R0", make_bridle_text([result]))

    def test_down_leg_is_the_hoist_high_hook(self):
        result = calculate_bridles(document(), outcome())[0]
        self.assertAlmostEqual(result["down_leg_force_n"], 85.91*9.80665,
                               places=3)
        self.assertAlmostEqual(result["down_leg_max_force_n"], 14709.97)
        self.assertNotIn("down_leg_overload", result)

    def test_unvalidated_hoist_load_blocks_the_bridle(self):
        result = calculate_bridles(document(), outcome("diagnostic_only"))[0]
        self.assertEqual(result["status"], "not_calculated")
        self.assertIn("connected_hoist_load_not_validated", result["issues"])
        self.assertEqual(evaluate_bridles([result])[0]["type"],
                         "bridle_not_calculated")

    def test_missing_anchor_fails_closed(self):
        model = document()
        model.house_rigging_points = model.house_rigging_points[2:]
        result = calculate_bridles(model, outcome())[0]
        self.assertIn("bridle_leg_anchors_not_found", result["issues"])
        self.assertEqual(result["legs"], [])

    def test_missing_anchor_is_an_error_marker(self):
        model = document()
        model.house_rigging_points = []
        result = calculate_bridles(model, outcome())[0]
        marker = evaluate_bridles([result])[0]
        self.assertEqual(marker["type"], "bridle_not_calculated")
        self.assertEqual(marker["severity"], "error")
        self.assertIn("bridle_leg_anchors_not_found", marker["message"])

    def test_leg_overload_is_marked(self):
        model = document()
        model.bridles[0].legs[0].max_force_n = 100.0
        result = calculate_bridles(model, outcome())[0]
        self.assertIn("bridle_leg_overload", result["issues"])
        self.assertEqual(evaluate_bridles([result])[0]["type"],
                         "bridle_leg_overload")


if __name__ == "__main__":
    unittest.main()
