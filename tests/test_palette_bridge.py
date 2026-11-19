import json
import os
import tempfile
import unittest

from rigcalc.vw.palette_bridge import (pending_settings_path,
                                       run_request_path,
                                       user_data_directory,
                                       write_json_atomic)


class PaletteBridgeTests(unittest.TestCase):
    def test_user_data_directory_matches_sdk_host(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(
                user_data_directory(root),
                os.path.join(root, "Nemetschek", "Vectorworks", "2027",
                             "RigCalc"))

    def test_control_files_share_the_user_data_directory(self):
        with tempfile.TemporaryDirectory() as root:
            directory = user_data_directory(root)
            self.assertEqual(run_request_path(root),
                             os.path.join(directory, "run_request.json"))
            self.assertEqual(pending_settings_path(root),
                             os.path.join(directory, "pending_settings.json"))

    def test_write_json_atomic_creates_directory_and_leaves_no_temp(self):
        payload = {"schema_version": 1, "hoists": [{"hoist_id": "M1"}]}
        with tempfile.TemporaryDirectory() as root:
            destination = os.path.join(root, "latest", "rigcalc_palette.json")

            result = write_json_atomic(payload, destination)

            self.assertEqual(result, destination)
            with open(destination, encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), payload)
            self.assertEqual(os.listdir(os.path.dirname(destination)),
                             ["rigcalc_palette.json"])


if __name__ == "__main__":
    unittest.main()
