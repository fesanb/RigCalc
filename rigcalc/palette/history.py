"""Comparison data for the palette's last two completed calculations."""

import json
import os


def _read_snapshot(path):
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def latest_archived_snapshot(project_root):
    """Return the newest usable archived palette snapshot, if any.

    ``runs`` is immutable, so it is the correct source for the comparison;
    ``latest`` is deliberately excluded because it is being replaced now.
    """
    if not project_root:
        return None
    runs_dir = os.path.join(project_root, "runs")
    try:
        names = sorted(os.listdir(runs_dir), reverse=True)
    except OSError:
        return None
    for name in names:
        snapshot = _read_snapshot(os.path.join(
            runs_dir, name, "rigcalc_palette.json"))
        if snapshot:
            snapshot["run_id"] = name
            return snapshot
    return None


def build_history(current_snapshot, project_root):
    """Summarize changes by stable drawing-object ID against the prior run."""
    previous = latest_archived_snapshot(project_root)
    if not previous:
        return {"available": False, "message": "No previous run."}
    before = {row.get("object_id"): row for row in previous.get("hoists", [])}
    after = {row.get("object_id"): row for row in current_snapshot.get("hoists", [])}
    changes = []
    for object_id in sorted(set(before) | set(after)):
        old, new = before.get(object_id), after.get(object_id)
        if old is None:
            changes.append({"object_id": object_id, "kind": "added",
                            "hoist_id": new.get("hoist_id", object_id)})
            continue
        if new is None:
            changes.append({"object_id": object_id, "kind": "removed",
                            "hoist_id": old.get("hoist_id", object_id)})
            continue
        fields = ("hoist_id", "status", "high_hook_mass_kg", "capacity_kg")
        delta = {
            field: {"before": old.get(field), "after": new.get(field)}
            for field in fields if old.get(field) != new.get(field)
        }
        if delta:
            changes.append({"object_id": object_id, "kind": "changed",
                            "hoist_id": new.get("hoist_id", object_id),
                            "changes": delta})
    return {
        "available": True,
        "previous_run_id": previous.get("run_id", ""),
        "previous_hoist_count": len(before),
        "current_hoist_count": len(after),
        "changes": changes,
    }
