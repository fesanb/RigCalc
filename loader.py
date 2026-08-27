"""Small Vectorworks Resource Manager entry point for LoadCalc."""

import importlib
import os
import sys
import tempfile
import traceback


ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run():
    import vs

    try:
        importlib.invalidate_caches()
        for module_name in list(sys.modules):
            if module_name == "loadcalc" or module_name.startswith("loadcalc."):
                del sys.modules[module_name]
        entry = importlib.import_module("loadcalc.main")
        entry.main()
    except Exception:
        error_dir = os.path.join(tempfile.gettempdir(), "VWDEV")
        os.makedirs(error_dir, exist_ok=True)
        error_path = os.path.join(error_dir, "loadcalc_error.txt")
        with open(error_path, "w", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())
        vs.AlrtDialog(
            "LoadCalc failed.\n\n"
            "Details were written to:\n{}".format(error_path)
        )


run()
