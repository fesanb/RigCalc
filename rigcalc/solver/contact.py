"""Shared tension-only contact-state load modelling."""


def engaged_contact_mass_loads(hoists):
    """Return point loads for hoist/chain mass at engaged contacts only."""
    result = []
    for attached in hoists:
        mass = attached.item.weight_with_chain_kg
        station = attached.attachment.global_station_mm
        if mass <= 0.0 or station is None:
            continue
        result.append({
            "source_id": "{}:contact_mass".format(attached.item.id),
            "source_type": "hoist_chain_contact_mass",
            "mass_kg": mass,
            "station_mm": station,
            "evidence": "BrxHoist.WeightWithChain; engaged_contact_state",
        })
    return result


def contact_mass_by_support(loads):
    """Index engaged-contact masses by hoist support ID."""
    return {
        item["source_id"].split(":", 1)[0]: item["mass_kg"]
        for item in loads if item.get("source_type") ==
        "hoist_chain_contact_mass"}
