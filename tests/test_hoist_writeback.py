import unittest

from rigcalc.model import DocumentModel, Point3D, Support
from rigcalc.vw.hoist_writeback import write_high_hook_values


class FakeVS:
    def __init__(self, proceed=True):
        self.proceed = proceed
        self.fields = {
            "ReactionForceWeight": "0", "ReactionForce": "0",
            "RoofForceNoDeadloadWeight": "0", "RoofForceNoDeadload": "0",
        }
        self.reset = []

    def YNDialog(self, message): return self.proceed
    def NameUndoEvent(self, name): pass
    def GetParametricRecord(self, handle): return "record"
    def GetName(self, record): return "BrxHoist"
    def NumFields(self, record): return len(self.fields)
    def GetFldName(self, record, index): return list(self.fields)[index - 1]
    def GetRField(self, handle, record, field): return self.fields[field]
    def SetRField(self, handle, record, field, value): self.fields[field] = value
    def ResetObject(self, handle): self.reset.append(handle)


class HoistWritebackTests(unittest.TestCase):
    def calculation(self):
        return {"constructions": [{
            "construction_id": "C1", "status": "preliminary",
            "writeback_eligible": True,
            "reactions": [{
                "support_id": "H1", "preliminary_high_hook_mass_kg": 123.4,
                "is_structural_link": False,
            }],
        }]}

    def test_cancel_writes_nothing(self):
        vs = FakeVS(proceed=False)
        document = DocumentModel(supports=[
            Support("H1", "Hoist", Point3D(0, 0), source_ref="handle")])
        result = write_high_hook_values(vs, document, self.calculation())
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(vs.fields["ReactionForceWeight"], "0")

    def test_writes_and_verifies_high_hook_fields(self):
        vs = FakeVS()
        document = DocumentModel(supports=[
            Support("H1", "Hoist", Point3D(0, 0), source_ref="handle")])
        result = write_high_hook_values(vs, document, self.calculation())
        self.assertEqual(result["status"], "written")
        self.assertEqual(vs.fields["ReactionForceWeight"], "123400.000000")
        self.assertEqual(vs.fields["ReactionForce"], "1210.140610")
        self.assertEqual(vs.reset, ["handle"])

    def test_automatic_mode_does_not_ask_for_confirmation(self):
        vs = FakeVS(proceed=False)
        document = DocumentModel(supports=[
            Support("H1", "Hoist", Point3D(0, 0), source_ref="handle")])
        result = write_high_hook_values(
            vs, document, self.calculation(), confirm=False)
        self.assertEqual(result["status"], "written")

    def test_ineligible_solver_result_is_not_written(self):
        vs = FakeVS()
        document = DocumentModel(supports=[
            Support("H1", "Hoist", Point3D(0, 0), source_ref="handle")])
        calculation = self.calculation()
        calculation["constructions"][0]["writeback_eligible"] = False
        result = write_high_hook_values(vs, document, calculation)
        self.assertEqual(result["status"], "nothing_to_write")
        self.assertEqual(vs.fields["ReactionForceWeight"], "0")

    def test_missing_eligibility_flag_is_not_written(self):
        vs = FakeVS()
        document = DocumentModel(supports=[
            Support("H1", "Hoist", Point3D(0, 0), source_ref="handle")])
        calculation = self.calculation()
        del calculation["constructions"][0]["writeback_eligible"]
        result = write_high_hook_values(vs, document, calculation)
        self.assertEqual(result["status"], "nothing_to_write")
        self.assertEqual(vs.fields["ReactionForceWeight"], "0")


if __name__ == "__main__":
    unittest.main()
