"""RIGCALC ISOLATED HOIST WRITE TEST

Copy this file into a separate Vectorworks Python Script resource. Select
exactly one Hoist before running it. This is not the normal RigCalc loader.
"""

import importlib
import os
import sys
import tempfile
import traceback

import vs


# Set this to the RigCalc folder containing the "rigcalc" package.
RIGCALC_REPO_DIR = r"C:\Path\To\RigCalc"


def run():
    try:
        marker = os.path.join(RIGCALC_REPO_DIR, "rigcalc", "__init__.py")
        if not os.path.isfile(marker):
            raise RuntimeError("RigCalc was not found:\n{}".format(marker))
        if RIGCALC_REPO_DIR not in sys.path:
            sys.path.insert(0, RIGCALC_REPO_DIR)
        importlib.invalidate_caches()
        for module_name in list(sys.modules):
            if module_name == "rigcalc" or module_name.startswith("rigcalc."):
                del sys.modules[module_name]
        probe = importlib.import_module("rigcalc.vw.write_probe")
        probe.run(vs)
    except Exception:
        error_dir = os.path.join(RIGCALC_REPO_DIR, "output")
        if not os.path.isdir(RIGCALC_REPO_DIR):
            error_dir = os.path.join(tempfile.gettempdir(), "VWDEV")
        os.makedirs(error_dir, exist_ok=True)
        error_path = os.path.join(error_dir, "rigcalc_write_test_error.txt")
        with open(error_path, "w", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())
        vs.AlrtDialog(
            "RigCalc write test failed.\n\nError log:\n{}".format(error_path))


run()
