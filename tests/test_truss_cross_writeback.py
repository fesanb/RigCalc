import unittest

from rigcalc.model import DocumentModel, Point3D, StructuralLink
from rigcalc.vw.truss_cross_writeback import write_truss_cross_forces


class FakeVS:
    def __init__(self, proceed=True):
        self.proceed = proceed
        self.fields = {"Force": "0"}
        self.reset = []

    def YNDialog(self, message): return self.proceed
    def NameUndoEvent(self, name): pass
    def GetParametricRecord(self, handle): return "record"
    def GetName(self, record): return "BrxCustomTrussCross"
    def NumFields(self, record): return len(self.fields)
    def GetFldName(self, record, index): return list(self.fields)[index-1]
    def GetRField(self, handle, record, field): return self.fields[field]
    def SetRField(self, handle, record, field, value): self.fields[field] = value
    def ResetObject(self, handle): self.reset.append(handle)


class TrussCrossWritebackTests(unittest.TestCase):
    def calculation(self, eligible=True):
        return {"constructions": [{
            "construction_id": "C1", "status": "preliminary",
            "writeback_eligible": eligible,
            "reactions": [{
                "support_id": "X1", "reaction_mass_kg": 125.0,
                "is_structural_link": True,
            }],
        }]}

    def document(self):
        return DocumentModel(structural_links=[StructuralLink(
            "X1", "Cross", Point3D(0, 0), "top", "bottom",
            source_ref="handle")])

    def test_writes_newtons_to_force_and_verifies_readback(self):
        vs = FakeVS()
        result = write_truss_cross_forces(
            vs, self.document(), self.calculation())
        self.assertEqual(result["status"], "written")
        self.assertEqual(vs.fields["Force"], "1225.831250")
        self.assertEqual(vs.reset, ["handle"])

    def test_ineligible_result_is_not_written(self):
        vs = FakeVS()
        result = write_truss_cross_forces(
            vs, self.document(), self.calculation(False))
        self.assertEqual(result["status"], "nothing_to_write")
        self.assertEqual(vs.fields["Force"], "0")

    def test_automatic_mode_does_not_ask_for_confirmation(self):
        vs = FakeVS(proceed=False)
        result = write_truss_cross_forces(
            vs, self.document(), self.calculation(), confirm=False)
        self.assertEqual(result["status"], "written")


if __name__ == "__main__":
    unittest.main()
