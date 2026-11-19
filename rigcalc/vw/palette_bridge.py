"""File handoff between the Vectorworks Python command and SDK palette host.

The calculation remains Python-owned.  The native palette reads the completed
result from the document's project store
(``<drawing>.rigcalc/latest/rigcalc_palette.json``, see ``project_store``) and
never receives Vectorworks handles or performs structural calculations.

Only two small, per-user control files live outside the project store, in
``%APPDATA%\\Nemetschek\\Vectorworks\\2027\\RigCalc``.  Their paths are
duplicated in ``sdk/vw2027/RigCalcPalette/Source/RigCalc/
PaletteSnapshotProvider.cpp`` and must be changed in both places together:

- ``pending_settings.json``: cable load and safety factor saved by the palette.
- ``run_request.json``: one-shot "run from palette" request, consumed here.
"""

import json
import os
import tempfile


VECTORWORKS_VERSION = "2027"
PENDING_SETTINGS_FILENAME = "pending_settings.json"
RUN_REQUEST_FILENAME = "run_request.json"


def user_data_directory(appdata_dir=None):
    """Return RigCalc's per-user Vectorworks directory, or ``None``."""
    root = appdata_dir or os.environ.get("APPDATA")
    if not root:
        return None
    return os.path.join(root, "Nemetschek", "Vectorworks",
                        VECTORWORKS_VERSION, "RigCalc")


def _user_file(filename, appdata_dir=None):
    directory = user_data_directory(appdata_dir)
    return os.path.join(directory, filename) if directory else None


def pending_settings_path(appdata_dir=None):
    return _user_file(PENDING_SETTINGS_FILENAME, appdata_dir)


def run_request_path(appdata_dir=None):
    return _user_file(RUN_REQUEST_FILENAME, appdata_dir)


def read_pending_settings():
    path = pending_settings_path()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def consume_run_request():
    """Return and remove a one-shot request made by the SDK palette."""
    path = run_request_path()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        os.unlink(path)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def write_json_atomic(payload, destination):
    """Write JSON so a concurrently reading palette never sees a partial file."""
    directory = os.path.dirname(destination)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".rigcalc_", suffix=".json", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, destination)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return destination
