import unittest
import tempfile

from rigcalc.vw.layer_dialog import candidate_layers, choose_calculation_layers


class FakeDialogVS:
    def __init__(self):
        self.states = {}
        self.closed = False
        self.alerts = []

    def CreateLayout(self, *args): return 1
    def CreateStaticText(self, *args): pass
    def SetFirstLayoutItem(self, *args): pass
    def SetBelowItem(self, *args): pass
    def CreateCheckBox(self, *args): pass
    def SetBooleanItem(self, dialog, item, state): self.states[item] = state
    def GetBooleanItem(self, dialog, item): return False if self.closed else self.states.get(item, False)
    def AlrtDialog(self, text): self.alerts.append(text)

    def RunLayoutDialog(self, dialog, handler):
        handler(12255, None)
        self.states[10] = True  # User checks the only layer.
        handler(1, None)
        self.closed = True
        return 1


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
            selected = choose_calculation_layers(vs, inventory, directory)
        self.assertEqual(selected, ["Rigging"])
        self.assertEqual(vs.alerts, [])


if __name__ == "__main__":
    unittest.main()
