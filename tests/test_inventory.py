import json
import unittest

from rigcalc.vw.inventory import scan_plugin_inventory


class FakeVS:
    def ForEachObject(self, callback, criteria):
        callback("handle")

    def GetParametricRecord(self, handle):
        return "pio_record"

    def GetName(self, handle):
        return {"pio_record": "BrxGenericWeight", "extra_record": "Load Info"}.get(handle, "Load A")

    def NumFields(self, record):
        return 1

    def GetFldName(self, record, index):
        return "Weight" if record == "pio_record" else "Note"

    def GetRField(self, handle, record_name, field_name):
        return "125 kg" if field_name == "Weight" else "diagnostic"

    def NumRecords(self, handle):
        return 2

    def GetRecord(self, handle, index):
        return ("pio_record", "extra_record")[index - 1]

    def GetTypeN(self, handle):
        return 86

    def GetClass(self, handle):
        return "Rigging"

    def GetLayer(self, handle):
        return "layer"

    def GetLName(self, handle):
        return "Design Layer-1"

    def GetSymLoc(self, handle):
        return 100.0, 200.0

    def Get3DCntr(self, handle):
        return 100.0, 200.0, 300.0


class InventoryTests(unittest.TestCase):
    def test_inventory_captures_all_records_and_fields(self):
        inventory = scan_plugin_inventory(FakeVS())
        self.assertEqual(len(inventory), 1)
        item = inventory[0]
        self.assertEqual(item["parametric_record"], "BrxGenericWeight")
        self.assertEqual(item["parametric_fields"]["Weight"], "125 kg")
        self.assertEqual([record["name"] for record in item["records"]], [
            "BrxGenericWeight", "Load Info"
        ])
        json.dumps(inventory)


if __name__ == "__main__":
    unittest.main()
