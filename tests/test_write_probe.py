import unittest

from rigcalc.vw.write_probe import FIELD_PROBES, run


class FakeVS:
    def __init__(self, handles=None, proceed=True):
        self.handles = handles or []
        self.proceed = proceed
        self.values = {
            field: "0" for field, _, _ in FIELD_PROBES}
        self.alerts = []
        self.events = []

    def FSActLayer(self):
        return self.handles[0] if self.handles else None

    def NextSObj(self, handle):
        try:
            return self.handles[self.handles.index(handle) + 1]
        except (ValueError, IndexError):
            return None

    def GetParametricRecord(self, handle):
        return "record"

    def GetName(self, record):
        return "BrxHoist"

    def NumFields(self, record):
        return len(FIELD_PROBES)

    def GetFldName(self, record, index):
        return FIELD_PROBES[index - 1][0]

    def GetRField(self, handle, record, field):
        return self.values[field]

    def SetRField(self, handle, record, field, value):
        self.values[field] = value

    def YNDialog(self, message):
        return self.proceed

    def AlrtDialog(self, message):
        self.alerts.append(message)

    def NameUndoEvent(self, name):
        self.events.append(("begin", name))

    def ResetObject(self, handle):
        self.events.append(("reset", handle))

class WriteProbeTests(unittest.TestCase):
    def test_requires_exactly_one_selected_hoist(self):
        vs = FakeVS()
        self.assertFalse(run(vs))
        self.assertIn("Selected Hoists: 0", vs.alerts[0])

    def test_writes_four_values_and_resets_object(self):
        vs = FakeVS(handles=["H1"])
        self.assertTrue(run(vs))
        self.assertEqual(
            vs.values,
            {field: value for field, value, _ in FIELD_PROBES})
        self.assertEqual(vs.events[-1], ("reset", "H1"))


if __name__ == "__main__":
    unittest.main()
