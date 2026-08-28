"""Verified Vectorworks BrxHoist structural-field mapping."""

# Confirmed by writing distinct values to a Vectorworks 2026 BrxHoist and
# observing the Structural section of the Object Info palette.
HIGH_HOOK_FORCE_FIELD = "ReactionForce"
HIGH_HOOK_WEIGHT_FIELD = "ReactionForceWeight"

# BrxHoist stores force as N and weight-equivalent mass as g.
STANDARD_GRAVITY_M_S2 = 9.80665


def high_hook_field_values(mass_kg):
    """Return raw BrxHoist field strings for a High Hook mass in kilograms."""
    return {
        HIGH_HOOK_WEIGHT_FIELD: "{:.6f}".format(mass_kg * 1000.0),
        HIGH_HOOK_FORCE_FIELD: "{:.6f}".format(
            mass_kg * STANDARD_GRAVITY_M_S2),
    }
