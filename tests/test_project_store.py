import json
import os
import tempfile
import unittest

from rigcalc.vw.project_store import (archive_latest, ensure_project,
                                      project_root)


class FakeVS:
    def __init__(self, path):
        self.path = path

    def GetFPathName(self):
        return self.path


class ProjectStoreTests(unittest.TestCase):
    def test_saved_document_uses_sibling_rigcalc_folder(self):
        with tempfile.TemporaryDirectory() as root:
            document = os.path.join(root, "Show.vwx")
            vs = FakeVS(document)

            latest = ensure_project(vs)

            store = os.path.join(root, "Show.rigcalc")
            self.assertEqual(latest, os.path.join(store, "latest"))
            with open(os.path.join(store, "manifest.json"),
                      encoding="utf-8") as stream:
                manifest = json.load(stream)
            self.assertEqual(manifest["document_path"], document)

    def test_unsaved_document_has_no_project_store(self):
        vs = FakeVS("")
        self.assertIsNone(project_root(vs))
        self.assertIsNone(ensure_project(vs))
        self.assertIsNone(archive_latest(vs))

    def test_latest_is_copied_to_immutable_run(self):
        with tempfile.TemporaryDirectory() as root:
            vs = FakeVS(os.path.join(root, "Show.vwx"))
            latest = ensure_project(vs)
            with open(os.path.join(latest, "snapshot.json"), "w",
                      encoding="utf-8") as stream:
                stream.write("{}")

            first = archive_latest(vs)
            second = archive_latest(vs)

            runs = os.path.join(root, "Show.rigcalc", "runs")
            self.assertEqual(os.path.dirname(first), runs)
            self.assertTrue(os.path.isfile(os.path.join(first, "snapshot.json")))
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
