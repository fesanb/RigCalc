import unittest

from rigcalc.model import DocumentModel, Point3D, Support
from rigcalc.notifications import (evaluate_deflections,
                                   evaluate_hoist_overloads,
                                   evaluate_internal_forces)
from rigcalc.vw.notifications import write_notification_markers


def reaction(load, capacity, support_id="H1", kind="hoist"):
    return {
        "support_id": support_id, "support_name": "Hoist",
        "support_hoist_id": "M01", "support_kind": kind,
        "reaction_mass_kg": load, "capacity_kg": capacity,
        "is_structural_link": False,
    }


def calculation(*reactions):
    return {"constructions": [{
        "construction_id": "C1", "status": "preliminary",
        "writeback_eligible": True, "reactions": list(reactions),
    }]}


class NotificationEvaluationTests(unittest.TestCase):
    def test_overload_becomes_load_error(self):
        items = evaluate_hoist_overloads(calculation(reaction(1100, 1000)))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["class_name"], "RigCalc-Load")
        self.assertEqual(items[0]["severity"], "error")
        self.assertAlmostEqual(items[0]["utilization"], 1.1)

    def test_capacity_uses_lower_hook_reaction_not_high_hook_mass(self):
        item = reaction(999, 1000)
        item["preliminary_high_hook_mass_kg"] = 1050
        self.assertEqual(evaluate_hoist_overloads(calculation(item)), [])

    def test_invalid_result_and_dead_hang_are_not_reported(self):
        invalid = calculation(reaction(1100, 1000))
        invalid["constructions"][0]["writeback_eligible"] = False
        self.assertEqual(evaluate_hoist_overloads(invalid), [])
        self.assertEqual(evaluate_hoist_overloads(
            calculation(reaction(1100, 1000, kind="dead_hang"))), [])

    def test_deflection_is_an_orange_informational_marker(self):
        value = calculation()
        value["constructions"][0]["deflection"] = {"spans": [{
            "span_start_mm": 0, "span_end_mm": 10000,
            "midspan": {"station_mm": 5000, "deflection_mm": -12},
            "maximum": {"station_mm": 5500, "deflection_mm": -13},
            "midspan_deflection_ratio": 10000/12,
        }]}
        items = evaluate_deflections(value)
        self.assertEqual(items[0]["class_name"], "RigCalc-Deflection")
        self.assertEqual(items[0]["source_station_mm"], 5500)

    def test_internal_force_over_capacity_becomes_blue_error(self):
        value = calculation()
        value["constructions"][0]["element_forces"] = [{
            "start_station_mm": 0, "end_station_mm": 5000,
            "cross_section": {"identifier": "TEST", "capacities": {
                "N_n": None, "Vy_n": None, "Vz_n": 10000,
                "T_nm": None, "My_nm": 8000, "Mz_nm": None}},
            "i": {"Vz_n": 9000, "My_nm": 9000},
            "j": {"Vz_n": 11000, "My_nm": 7000},
        }]
        items = evaluate_internal_forces(value)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item["class_name"] == "RigCalc-Internal"
                            for item in items))
        self.assertIn("My 9.00/8.00 kNm", items[0]["message"])
        self.assertIn("Vz 11.00/10.00 kN", items[1]["message"])


class FakeVS:
    def __init__(self):
        self.classes = {"None", "RigCalc-Load"}
        self.active_class = "None"
        self.objects = {
            "old": {"name": "__RigCalcNotification__old",
                    "class": "RigCalc-Load"},
            "user": {"name": "User note", "class": "RigCalc-Load"},
        }
        self.last = None
        self.class_attributes = {}

    def ActiveClass(self): return self.active_class
    def GetObject(self, name):
        return "class:" + name if name in self.classes else None
    def GetTypeN(self, handle):
        return 94 if handle.startswith("class:") else 0
    def NameClass(self, name):
        self.classes.add(name); self.active_class = name
    def SetClFillFore(self, name, color):
        self.class_attributes.setdefault(name, {})["fill_fore"] = color
    def SetClFillBack(self, name, color):
        self.class_attributes.setdefault(name, {})["fill_back"] = color
    def SetClFPat(self, name, pattern):
        self.class_attributes.setdefault(name, {})["fill_pattern"] = pattern
    def SetClPenFore(self, name, color):
        self.class_attributes.setdefault(name, {})["pen_fore"] = color
    def SetClPenBack(self, name, color):
        self.class_attributes.setdefault(name, {})["pen_back"] = color
    def SetClUseGraphic(self, name, value):
        self.class_attributes.setdefault(name, {})["use_graphic"] = value
    def SetClLSN(self, name, value):
        self.class_attributes.setdefault(name, {})["line_style"] = value
    def SetClLW(self, name, value):
        self.class_attributes.setdefault(name, {})["line_weight"] = value
    def SetClOpacity(self, name, value):
        self.class_attributes.setdefault(name, {})["opacity"] = value
    def ForEachObject(self, callback, criteria):
        class_name = criteria.split("'")[1]
        for handle, item in list(self.objects.items()):
            if item["class"] == class_name: callback(handle)
    def GetName(self, handle): return self.objects[handle]["name"]
    def NameUndoEvent(self, name): pass
    def DelObject(self, handle): del self.objects[handle]
    def TextOrigin(self, x, y): self.origin = (x, y)
    def CreateText(self, value):
        self.last = "text"; self.objects[self.last] = {
            "name": "", "class": self.active_class, "text": value}
    def LNewObj(self): return self.last
    def SetClass(self, handle, name): self.objects[handle]["class"] = name
    def SetName(self, handle, name): self.objects[handle]["name"] = name
    def SetFillColorByClass(self, handle): self.objects[handle]["fill_by_class"] = True
    def SetFPatByClass(self, handle): self.objects[handle]["fpat_by_class"] = True
    def SetPenColorByClass(self, handle): self.objects[handle]["pen_by_class"] = True
    def SetTextWrap(self, handle, value): self.objects[handle]["wrap"] = value
    def SetObjectVariableBoolean(self, handle, selector, value):
        self.objects[handle]["boolean:{}".format(selector)] = value


class NotificationWriterTests(unittest.TestCase):
    def test_reconciles_owned_markers_and_preserves_user_objects(self):
        vs = FakeVS()
        document = DocumentModel(supports=[Support(
            "H1", "Hoist", Point3D(100, 200), hoist_id="M01")])
        notifications = evaluate_hoist_overloads(
            calculation(reaction(1100, 1000)))
        result = write_notification_markers(vs, document, [], notifications)
        self.assertEqual(result["removed_count"], 1)
        self.assertIn("user", vs.objects)
        self.assertEqual(vs.objects["text"]["class"], "RigCalc-Load")
        self.assertTrue(vs.objects["text"]["fill_by_class"])
        self.assertTrue(vs.objects["text"]["fpat_by_class"])
        self.assertTrue(vs.objects["text"]["pen_by_class"])
        self.assertFalse(vs.objects["text"]["wrap"])
        self.assertFalse(vs.objects["text"]["boolean:684"])
        self.assertEqual(vs.objects["text"]["text"],
                         "OVERLOAD\nM01\n1100 / 1000 kg (110 %)")
        self.assertEqual(vs.origin, (600.0, 700.0))
        self.assertEqual(vs.active_class, "None")

    def test_new_classes_get_defaults_without_overwriting_existing_class(self):
        vs = FakeVS()
        document = DocumentModel(supports=[Support(
            "H1", "Hoist", Point3D(0, 0), hoist_id="M01")])
        write_notification_markers(vs, document, [], [])
        self.assertNotIn("RigCalc-Load", vs.class_attributes)
        self.assertEqual(
            vs.class_attributes["RigCalc-Deflection"]["fill_fore"],
            (65535, 32768, 0))
        self.assertEqual(
            vs.class_attributes["RigCalc-Internal"]["fill_fore"],
            (0, 19660, 52428))
        self.assertEqual(
            vs.class_attributes["RigCalc-Internal"]["pen_fore"],
            (65535, 65535, 65535))
        self.assertTrue(
            vs.class_attributes["RigCalc-Internal"]["use_graphic"])
        self.assertEqual(
            vs.class_attributes["RigCalc-Internal"]["line_style"], 2)
        self.assertEqual(
            vs.class_attributes["RigCalc-Internal"]["line_weight"], 5)
        self.assertEqual(
            vs.class_attributes["RigCalc-Internal"]["opacity"], 100)


if __name__ == "__main__":
    unittest.main()
