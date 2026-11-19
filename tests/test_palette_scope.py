import json
import os
import tempfile
import unittest
from unittest import mock

from rigcalc.vw.layer_dialog import scope_from_palette_request


class PaletteScopeTests(unittest.TestCase):
    def test_palette_reuses_reviewed_layers_and_pending_settings(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with open(os.path.join(output_dir, "rigcalc_layer_selection.json"),
                      "w", encoding="utf-8") as stream:
                json.dump({"included_layers": ["Rigging"],
                           "cable_load_kg_m": 0.0, "safety_factor": 1.0},
                          stream)
            with mock.patch(
                    "rigcalc.vw.layer_dialog.read_pending_settings",
                    return_value={"cable_load_kg_m": 1.25,
                                  "safety_factor": 1.2}):
                scope = scope_from_palette_request(
                    output_dir, {"run_from_palette": True})

        self.assertEqual(scope, {"selected": ["Rigging"],
                                 "cable_load_kg_m": 1.25,
                                 "safety_factor": 1.2})

    def test_palette_never_guesses_layers(self):
        with tempfile.TemporaryDirectory() as output_dir:
            self.assertIsNone(scope_from_palette_request(
                output_dir, {"run_from_palette": True}))

    def test_menu_run_is_not_a_palette_request(self):
        with tempfile.TemporaryDirectory() as output_dir:
            self.assertIsNone(scope_from_palette_request(output_dir, {}))


if __name__ == "__main__":
    unittest.main()
