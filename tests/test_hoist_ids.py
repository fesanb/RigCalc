import unittest

from rigcalc.vw.hoist_ids import populate_missing_hoist_ids


class FakeVS:
    def __init__(self):
        self.data = {
            "h1": {"HoistID": "M1", "OriginX": "100", "OriginY": "0"},
            "h2": {"HoistID": "", "OriginX": "200", "OriginY": "0"},
        }

    def ForEachObject(self, callback, _criteria):
        for handle in self.data:
            callback(handle)

    def GetParametricRecord(self, handle):
        return ("record", handle)

    def GetName(self, record):
        return "BrxHoist" if isinstance(record, tuple) else ""

    def NumFields(self, _record):
        return 3

    def GetFldName(self, _record, index):
        return ("HoistID", "OriginX", "OriginY")[index-1]

    def GetRField(self, handle, _record_name, field):
        return self.data[handle][field]

    def SetRField(self, handle, _record_name, field, value):
        self.data[handle][field] = value

    def ResetObject(self, _handle):
        pass

    def NameUndoEvent(self, _name):
        pass


class HoistIdTests(unittest.TestCase):
    def test_existing_id_is_preserved_and_blank_gets_next_free_m_number(self):
        vs = FakeVS()
        result = populate_missing_hoist_ids(vs)
        self.assertEqual(vs.data["h1"]["HoistID"], "M1")
        self.assertEqual(vs.data["h2"]["HoistID"], "M2")
        self.assertEqual(result["assigned_count"], 1)
        self.assertEqual(result["items"][0]["status"], "written")


if __name__ == "__main__":
    unittest.main()
