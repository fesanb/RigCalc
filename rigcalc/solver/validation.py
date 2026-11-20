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


def guarded_solve(solver, construction, loads, method, **kwargs):
    """Run one construction solver without letting it abort the whole run.

    An unexpected exception is a defect in RigCalc, not a calculation result.
    It is reported as an explicit, writeback-blocked ``not_calculated``
    construction with the error text, so its hoists receive a 0.00 kN outcome
    with that reason and every other construction is still calculated.
    """
    try:
        return solver(construction, loads, **kwargs)
    except Exception as error:  # noqa: BLE001 - fail closed per construction
        import traceback
        return {
            "construction_id": construction.id,
            "construction_name": getattr(construction, "label",
                                         construction.id),
            "status": "not_calculated",
            "method": method,
            "loads": loads,
            "writeback_eligible": False,
            "load_transfer_eligible": False,
            "total_applied_mass_kg": sum(
                item.get("mass_kg", 0.0) for item in loads),
            "reactions": [], "stations": [], "element_forces": [],
            "issues": ["internal_solver_error:{}: {}".format(
                type(error).__name__, error)],
            "internal_error_traceback": traceback.format_exc(),
        }
