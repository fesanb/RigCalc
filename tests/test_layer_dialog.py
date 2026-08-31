import unittest
import tempfile
import os

from rigcalc.vw.layer_dialog import (candidate_layers,
                                      choose_calculation_scope,
                                      preflight_context)


class FakeDialogVS:
    def __init__(self):
        self.states = {}
        self.text = {}
        self.closed = False
        self.alerts = []

    def CreateLayout(self, *args): return 1
    def GetFName(self): return "Representative rig.vwx"
    def CreateStaticText(self, *args): pass
    def SetFirstLayoutItem(self, *args): pass
    def SetBelowItem(self, *args): pass
    def CreateCheckBox(self, *args): pass
    def CreateEditText(self, dialog, item, value, width): self.text[item] = value
    def SetRightItem(self, *args): pass
    def SetItemText(self, dialog, item, value): self.text[item] = value
    def GetItemText(self, dialog, item): return self.text.get(item, "")
    def SetBooleanItem(self, dialog, item, state): self.states[item] = state
    def GetBooleanItem(self, dialog, item): return False if self.closed else self.states.get(item, False)
    def AlrtDialog(self, text): self.alerts.append(text)

    def RunLayoutDialog(self, dialog, handler):
        handler(12255, None)
        self.states[100] = True  # User checks the only layer.
        self.text[8] = "2,00"
        self.text[20] = "1,10"
        handler(1, None)
        self.closed = True
        return 1


class CancelDialogVS(FakeDialogVS):
    def RunLayoutDialog(self, dialog, handler):
        handler(12255, None)
        return 2


class LayerDialogTests(unittest.TestCase):
    def test_only_layers_with_calculation_relevant_pios_are_offered(self):
        inventory = [
            {"layer_name": "Rigging", "parametric_record": "TrussItem"},
            {"layer_name": "Lights floor", "parametric_record": "Lighting Device"},
            {"layer_name": "Sheet 1", "parametric_record": "Title Block Border"},
            {"layer_name": "Overview", "parametric_record": "NNA_DesignLayerViewport"},
        ]
        self.assertEqual(candidate_layers(inventory), ["Lights floor", "Rigging"])

    def test_selection_is_read_before_dialog_is_destroyed(self):
        vs = FakeDialogVS()
        inventory = [{"layer_name": "Rigging", "parametric_record": "TrussItem"}]
        with tempfile.TemporaryDirectory() as directory:
            scope = choose_calculation_scope(vs, inventory, directory)
        self.assertEqual(scope["selected"], ["Rigging"])
        self.assertEqual(scope["cable_load_kg_m"], 2.0)
        self.assertEqual(scope["safety_factor"], 1.1)
        self.assertEqual(vs.alerts, [])

    def test_preflight_context_is_shallow_and_marks_saved_selection_as_suggestion(self):
        context = preflight_context(FakeDialogVS(), [
            {"layer_name": "Rigging", "parametric_record": "TrussItem"},
            {"layer_name": "Rigging", "parametric_record": "BrxHoist"},
        ], {"Rigging"})
        self.assertEqual(context["document_name"], "Representative rig.vwx")
        self.assertEqual(context["relevant_object_count"], 2)
        self.assertTrue(context["previous_selection_available"])

    def test_cancel_does_not_persist_a_selection(self):
        inventory = [{"layer_name": "Rigging", "parametric_record": "TrussItem"}]
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(choose_calculation_scope(
                CancelDialogVS(), inventory, directory))
            self.assertFalse(os.path.exists(
                os.path.join(directory, "rigcalc_layer_selection.json")))

    def test_no_relevant_layers_stops_before_creating_a_dialog(self):
        vs = FakeDialogVS()
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(choose_calculation_scope(vs, [{
                "layer_name": "Sheet", "parametric_record": "Title Block Border",
            }], directory))
        self.assertIn("no layers", vs.alerts[0].lower())


if __name__ == "__main__":
    unittest.main()
