"""Bridle and house rigging point force writeback (fail closed, verified)."""

import unittest

from rigcalc.solver.bridle import calculate_bridles
from rigcalc.vw.bridle_writeback import write_bridle_forces
from tests.test_bridle import document, outcome


class FieldVS:
    def __init__(self, records):
        self.records = records          # handle -> (record, fields)
        self.undo = []

    def NameUndoEvent(self, name):
        self.undo.append(name)

    def SetRField(self, handle, record, field, value):
        self.records[handle][1][field] = value

    def ResetObject(self, handle):
        pass


def patched_document():
    model = document()
    model.bridles[0].source_ref = "bridle"
    for point in model.house_rigging_points:
        point.source_ref = point.id
    return model


class BridleWritebackTests(unittest.TestCase):
    def run_writeback(self, results, model):
        records = {"bridle": ("BridleObj", {})}
        for point in model.house_rigging_points:
            records[point.id] = ("HouseRiggingPoint", {})
        vs = FieldVS(records)
        import rigcalc.vw.bridle_writeback as module
        original = module.get_parametric_info
        module.get_parametric_info = lambda _vs, handle: records[handle]
        try:
            return write_bridle_forces(vs, model, results), records, vs
        finally:
            module.get_parametric_info = original

    def test_calculated_bridle_writes_legs_and_house_points(self):
        model = patched_document()
        results = calculate_bridles(model, outcome())
        written, records, vs = self.run_writeback(results, model)
        self.assertEqual(written["status"], "written", written)
        self.assertEqual(vs.undo, ["RigCalc bridle force writeback"])
        legs = records["bridle"][1]
        self.assertAlmostEqual(float(legs["ForceLeg1"]), 513.7, delta=1.0)
        self.assertAlmostEqual(float(legs["ForceLeg2"]), 561.6, delta=1.0)
        self.assertAlmostEqual(float(legs["ForceDownLeg"]), 85.91*9.80665,
                               delta=0.01)
        point = records["R0"][1]
        self.assertAlmostEqual(float(point["ForceZ"]), -502.1, delta=1.0)
        self.assertNotIn("ForceZ", records["R2"][1])

    def test_uncalculated_bridle_writes_nothing(self):
        model = patched_document()
        results = calculate_bridles(model, outcome("diagnostic_only"))
        written, records, vs = self.run_writeback(results, model)
        self.assertEqual(written["status"], "nothing_to_write")
        self.assertEqual(records["bridle"][1], {})
        self.assertEqual(vs.undo, [])


if __name__ == "__main__":
    unittest.main()
