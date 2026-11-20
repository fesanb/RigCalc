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


# Vertical displacement tolerance, in metres, for a released hoist contact.
RELEASED_CONTACT_UZ_TOLERANCE_M = 1.0e-8
RELEASED_CONTACT_RULE = "released hoist uz_m >= -1e-8 (pickup rises; chain slack)"


def released_contact_is_slack(uz_m):
    """Return whether a released hoist pickup is compatible with slack chain.

    A chain hangs from the motor above the truss and can only pull upward.
    It is slack only when the pickup rises toward the motor (or stays put);
    a pickup that moves down would stretch an inextensible chain, so that
    contact must be engaged.  ``uz_m`` is positive upward.  A missing
    displacement is never accepted as slack.
    """
    return uz_m is not None and uz_m >= -RELEASED_CONTACT_UZ_TOLERANCE_M
