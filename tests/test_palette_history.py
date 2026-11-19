import unittest

from rigcalc.palette.history import build_history


class PaletteHistoryTests(unittest.TestCase):
    def test_compares_current_snapshot_with_latest_immutable_run(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "Show.rigcalc"
            runs = root / "runs" / "2026-01-01_000000Z"
            runs.mkdir(parents=True)
            (runs / "rigcalc_palette.json").write_text(
                '{"hoists":[{"object_id":"H1","hoist_id":"M1",'
                '"status":"calculated","high_hook_mass_kg":100,"capacity_kg":500}]}',
                encoding="utf-8")
            current = {"hoists": [
                {"object_id": "H1", "hoist_id": "M1", "status": "calculated",
                 "high_hook_mass_kg": 110, "capacity_kg": 500},
                {"object_id": "H2", "hoist_id": "M2"},
            ]}
            history = build_history(current, str(root))
        self.assertTrue(history["available"])
        self.assertEqual(history["previous_run_id"], "2026-01-01_000000Z")
        self.assertEqual({item["kind"] for item in history["changes"]},
                         {"changed", "added"})
