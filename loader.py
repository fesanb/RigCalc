"""RIGCALC VECTORWORKS LOADER

Copy the complete contents of this file into a Python Script resource in
Vectorworks. Normally, only RIGCALC_REPO_DIR needs to be changed.
"""

import importlib
import os
import sys
import tempfile
import traceback

import vs


# ===========================================================================
# USER CONFIGURATION - CHANGE THIS PATH FOR EACH COMPUTER
# ===========================================================================
# Set this to the RigCalc folder that contains the "rigcalc" package.
# The path must end in \RigCalc, NOT in \VWDEV or \RigCalc\rigcalc.

RIGCALC_REPO_DIR = (
    r"C:\Path\To\RigCalc"
)

# ===========================================================================
# END USER CONFIGURATION - DO NOT CHANGE ANYTHING BELOW DURING NORMAL USE
# ===========================================================================


def run():
    try:
        package_marker = os.path.join(
            RIGCALC_REPO_DIR, "rigcalc", "__init__.py"
        )
        if not os.path.isfile(package_marker):
            raise RuntimeError(
                "RigCalc was not found. Check RIGCALC_REPO_DIR.\n\n"
                "Expected file:\n{}".format(package_marker)
            )

        if RIGCALC_REPO_DIR not in sys.path:
            sys.path.insert(0, RIGCALC_REPO_DIR)

        importlib.invalidate_caches()

        # Load every saved code change without restarting Vectorworks.
        for module_name in list(sys.modules):
            if module_name == "rigcalc" or module_name.startswith("rigcalc."):
                del sys.modules[module_name]

        entry = importlib.import_module("rigcalc.main")
        entry.main()

    except Exception:
        error_dir = os.path.join(tempfile.gettempdir(), "VWDEV")
        os.makedirs(error_dir, exist_ok=True)
        error_path = os.path.join(error_dir, "rigcalc_error.txt")
        with open(error_path, "w", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())

        vs.AlrtDialog(
            "RigCalc failed.\n\n"
            "Check the loader path and error log:\n{}".format(error_path)
        )


run()
