"""Adapter from RigCalc's calculation model to palette-facing data.

The solver reports remain the engineering record.  This adapter provides the
small, stable view model needed by an interactive UI without serializing
opaque Vectorworks handles into a report file.
"""

from dataclasses import dataclass


GRAVITY_KN_PER_KG = 9.80665 / 1000.0
SNAPSHOT_VERSION = 1


def _position(point):
    if point is None:
        return None
    return {"x_mm": point.x, "y_mm": point.y, "z_mm": point.z}


def _kn(mass_kg):
    return None if mass_kg is None else mass_kg * GRAVITY_KN_PER_KG


def _reaction_index(calculation):
    index = {}
    for construction in calculation.get("constructions", []):
        for reaction in construction.get("reactions", []):
            if (reaction.get("support_kind") == "hoist" and
                    not reaction.get("is_structural_link")):
                index[reaction.get("support_id")] = (construction, reaction)
    return index


def _load_rows(construction):
    """Return source load evidence already used by the selected solver."""
    rows = []
    for load in construction.get("loads", []):
        mass_kg = load.get("mass_kg")
        rows.append({
            "source_id": load.get("source_id", ""),
            "source_type": load.get("source_type", ""),
            "mass_kg": mass_kg,
            "force_kn": _kn(mass_kg),
            "station_mm": load.get("station_mm"),
            "interval_start_mm": load.get("interval_start_mm"),
            "interval_end_mm": load.get("interval_end_mm"),
            "evidence": load.get("evidence", ""),
        })
    return rows


@dataclass
class PaletteRun:
    """One completed calculation kept alive for an interactive palette.

    ``snapshot`` is safe to send to a web UI or write to JSON.  ``object_refs``
    intentionally remains in-process, because Vectorworks handles are opaque
    and invalid outside the open document session.
    """

    snapshot: dict
    object_refs: dict

    def source_ref(self, object_id):
        """Return the current Vectorworks handle for a palette object ID."""
        return self.object_refs.get(object_id)


def build_palette_run(document, calculation, hoist_outcomes, notifications,
                      calculation_settings=None, document_context=None):
    """Build the palette contract and live-object index for one completed run."""
    outcomes = {item["support_id"]: item for item in hoist_outcomes}
    reactions = _reaction_index(calculation)
    object_refs = {}
    hoists = []
    system_labels = {}
    for truss in document.trusses:
        if truss.vw_truss_system and (truss.source_position_name or truss.name):
            system_labels.setdefault(
                truss.vw_truss_system, truss.source_position_name or truss.name)

    for support in document.supports:
        if support.support_kind != "hoist":
            continue
        object_refs[support.id] = support.source_ref
        outcome = outcomes.get(support.id, {
            "support_id": support.id,
            "status": "zero_not_calculated",
            "reaction_mass_kg": 0.0,
            "high_hook_mass_kg": 0.0,
            "writeback_eligible": False,
            "reason": "missing_hoist_outcome",
        })
        construction, reaction = reactions.get(support.id, ({}, {}))
        reaction_mass_kg = outcome.get("reaction_mass_kg", 0.0)
        high_hook_mass_kg = outcome.get("high_hook_mass_kg", 0.0)
        hoists.append({
            "object_id": support.id,
            "object_uuid": support.object_uuid,
            "hoist_id": support.hoist_id,
            "name": support.name,
            "motor_type": support.motor_type or support.name,
            "position": _position(support.position),
            "status": outcome.get("status"),
            "reason": outcome.get("reason", ""),
            "construction_id": outcome.get(
                "construction_id", construction.get("construction_id", "")),
            "truss_system_name": system_labels.get(support.vw_truss_system, ""),
            "writeback_eligible": bool(outcome.get("writeback_eligible")),
            "reaction_mass_kg": reaction_mass_kg,
            "reaction_force_kn": _kn(reaction_mass_kg),
            "high_hook_mass_kg": high_hook_mass_kg,
            "high_hook_force_kn": _kn(high_hook_mass_kg),
            "hoist_and_chain_mass_kg": reaction.get(
                "hoist_and_chain_mass_kg", support.weight_with_chain_kg),
            "capacity_kg": reaction.get("capacity_kg", support.capacity_kg),
            "unconstrained_reaction_mass_kg": reaction.get(
                "unconstrained_reaction_mass_kg"),
            "loads": _load_rows(construction),
            "association_evidence": outcome.get("association_evidence"),
            "association_diagnostic": outcome.get("association_diagnostic"),
            "status_explanation": {
                "status": outcome.get("status"),
                "reason": outcome.get("reason", ""),
                "writeback_eligible": bool(outcome.get("writeback_eligible")),
                "unconstrained_reaction_mass_kg": reaction.get(
                    "unconstrained_reaction_mass_kg"),
                "association_evidence": outcome.get("association_evidence"),
                "association_diagnostic": outcome.get("association_diagnostic"),
            },
        })

    for collection in (document.point_loads, document.distributed_loads,
                       document.trusses, document.structural_links):
        for item in collection:
            object_refs[item.id] = item.source_ref

    warning_rows = []
    for notification in notifications:
        warning_rows.append({
            "id": notification.get("id", ""),
            "type": notification.get("type", ""),
            "severity": notification.get("severity", ""),
            "message": notification.get("message", ""),
            "support_id": notification.get("support_id", ""),
            "construction_id": notification.get("construction_id", ""),
            "source_station_mm": notification.get("source_station_mm"),
        })

    snapshot = {
        "schema_version": SNAPSHOT_VERSION,
        "document": document_context or {},
        "calculation_settings": calculation_settings or {},
        "hoists": sorted(hoists, key=lambda row: (
            row["hoist_id"] or row["name"] or row["object_id"])),
        "warnings": warning_rows,
    }
    return PaletteRun(snapshot=snapshot, object_refs=object_refs)
