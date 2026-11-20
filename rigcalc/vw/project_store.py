"""Per-document, auditable storage for RigCalc calculations."""

import json
import os
import shutil
from datetime import datetime, timezone


def document_path(vs):
    """Return the saved Vectorworks document path, never a guessed path."""
    try:
        path = vs.GetFPathName() if hasattr(vs, "GetFPathName") else ""
    except Exception:
        return None
    path = str(path or "")
    # A bare file name (no folder) is not a saved location: resolving it
    # against the working directory put the project store under
    # C:\Program Files and failed with "Access denied".
    if not path or not os.path.isabs(path):
        return None
    return os.path.normpath(path)


def project_root(vs):
    path = document_path(vs)
    if not path:
        return None
    stem, _ = os.path.splitext(path)
    return stem + ".rigcalc"


def latest_directory(vs):
    root = project_root(vs)
    return os.path.join(root, "latest") if root else None


def ensure_project(vs):
    root = project_root(vs)
    if not root:
        return None
    latest = os.path.join(root, "latest")
    os.makedirs(latest, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "document_path": document_path(vs),
        "project_root": root,
    }
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return latest


def archive_latest(vs):
    root = project_root(vs)
    latest = latest_directory(vs)
    if not root or not latest:
        return None
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")
    destination = os.path.join(root, "runs", run_id)
    suffix = 2
    while os.path.exists(destination):
        destination = os.path.join(root, "runs", "{}_{}".format(run_id, suffix))
        suffix += 1
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copytree(latest, destination)
    return destination
