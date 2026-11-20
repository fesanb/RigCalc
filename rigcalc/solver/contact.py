"""Shared tension-only hoist contact rules.

Hoist/chain mass (``WeightWithChain``) is never applied to the truss.  It
always ends in the top hook, whatever the hoist orientation, so
High Hook = truss reaction + WeightWithChain.  The truss reaction alone
decides whether a chain is taut or slack.
"""


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
