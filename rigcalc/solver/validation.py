"""Result-eligibility rules shared by solver orchestration.

The flags deliberately distinguish a solved result from one that is safe to
propagate as a load to another construction.
"""


def load_transfer_eligible(result):
    """Return whether a result is an approved upstream load source."""
    return bool(result.get("load_transfer_eligible", False))


def finalize_eligibility(result, support_model_valid, numerical_valid=True,
                         load_model_valid=True, permit_writeback=True,
                         permit_load_transfer=None):
    """Record validation levels and derive writeback/transfer eligibility.

    Force and moment equilibrium are necessary but cannot alone demonstrate a
    mechanically meaningful result.  Solver adapters supply the remaining
    model-specific checks explicitly.
    """
    validation = result.setdefault("validation", {})
    calculated = result.get("status") == "preliminary"
    equilibrium_valid = bool(
        validation.get("vertical_equilibrium_ok") and
        validation.get("moment_equilibrium_ok"))
    validation.update({
        "calculated": calculated,
        "equilibrium_valid": equilibrium_valid,
        "support_model_valid": bool(support_model_valid),
        "numerically_valid": bool(numerical_valid),
        "load_model_valid": bool(load_model_valid),
    })
    eligible = bool(
        permit_writeback and calculated and equilibrium_valid and
        support_model_valid and numerical_valid and load_model_valid)
    if permit_load_transfer is None:
        permit_load_transfer = permit_writeback
    result["writeback_eligible"] = eligible
    result["load_transfer_eligible"] = bool(
        eligible and permit_load_transfer)
    return eligible
