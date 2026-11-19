import unittest

from rigcalc.model import DocumentModel, Point3D, Support
from rigcalc.palette import build_palette_run
from rigcalc.vw.palette_session import (clear_active_palette_run,
                                        get_active_palette_run,
                                        set_active_palette_run)


class PaletteSnapshotTests(unittest.TestCase):
    def tearDown(self):
        clear_active_palette_run()

    def test_snapshot_explains_top_hook_and_keeps_handle_in_process(self):
        handle = object()
        hoist = Support("H1", "Motor left", Point3D(100, 200, 300),
                        hoist_id="M01", capacity_kg=500.0,
                        weight_with_chain_kg=10.0, source_ref=handle)
        calculation = {"constructions": [{
            "construction_id": "C1", "issues": ["contact_model_pending"],
            "loads": [{"source_id": "L1", "source_type": "Lighting Device",
                       "mass_kg": 100.0, "station_mm": 1200.0,
                       "evidence": "geometry_sphere"}],
            "reactions": [{"support_id": "H1", "support_kind": "hoist",
                           "is_structural_link": False,
                           "hoist_and_chain_mass_kg": 10.0,
                           "capacity_kg": 500.0,
                           "unconstrained_reaction_mass_kg": 95.0}],
        }]}
        outcomes = [{"support_id": "H1", "hoist_id": "M01",
                     "status": "diagnostic_only", "construction_id": "C1",
                     "reaction_mass_kg": 100.0, "high_hook_mass_kg": 110.0,
                     "writeback_eligible": False,
                     "reason": "contact_model_pending"}]

        run = build_palette_run(DocumentModel(supports=[hoist]), calculation,
                                outcomes, notifications=[],
                                calculation_settings={"cable_load_kg_m": 2.5,
                                                      "safety_factor": 1.2})

        row = run.snapshot["hoists"][0]
        self.assertEqual(row["hoist_id"], "M01")
        self.assertAlmostEqual(row["high_hook_force_kn"], 1.0787315)
        self.assertEqual(row["loads"][0]["source_id"], "L1")
        self.assertFalse(row["writeback_eligible"])
        self.assertEqual(run.snapshot["calculation_settings"]["cable_load_kg_m"], 2.5)
        self.assertIs(run.source_ref("H1"), handle)

    def test_zero_outcome_remains_explicit_in_palette(self):
        hoist = Support("H1", "Motor", Point3D(0, 0), hoist_id="M01")
        outcome = {"support_id": "H1", "status": "zero_not_calculated",
                   "reaction_mass_kg": 0.0, "high_hook_mass_kg": 0.0,
                   "writeback_eligible": False,
                   "reason": "ambiguous_geometry_attachment"}
        run = build_palette_run(DocumentModel(supports=[hoist]),
                                {"constructions": []}, [outcome], [])
        row = run.snapshot["hoists"][0]
        self.assertEqual(row["high_hook_force_kn"], 0.0)
        self.assertEqual(row["reason"], "ambiguous_geometry_attachment")

    def test_session_replaces_previous_run_and_can_be_cleared(self):
        first = object()
        second = object()
        set_active_palette_run(first)
        set_active_palette_run(second)
        self.assertIs(get_active_palette_run(), second)
        clear_active_palette_run()
        self.assertIsNone(get_active_palette_run())


if __name__ == "__main__":
    unittest.main()
