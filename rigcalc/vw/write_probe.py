"""Isolated Vectorworks field probe. Never called by normal RigCalc runs."""

from .records import get_parametric_info


FIELD_PROBES = (
    ("ReactionForceWeight", "1000", "1 = High Hook Weight Equivalent"),
    ("ReactionForce", "2000", "2 = High Hook Force"),
    ("RoofForceNoDeadloadWeight", "3000", "3 = Low Hook Weight Equivalent"),
    ("RoofForceNoDeadload", "4000", "4 = Low Hook Force"),
)


def _selected_hoists(vs):
    handles = []
    # SEL=TRUE also finds selected state inside nested Spotlight structures.
    # FSActLayer/NextSObj walks only the user's active, top-level selection.
    handle = vs.FSActLayer()
    while handle:
        record_name, _ = get_parametric_info(vs, handle)
        if record_name == "BrxHoist":
            handles.append(handle)
        handle = vs.NextSObj(handle)
    return handles


def run(vs_module=None):
    if vs_module is None:
        import vs as vs_module
    handles = _selected_hoists(vs_module)
    if len(handles) != 1:
        vs_module.AlrtDialog(
            "RigCalc write test\n\nSelect exactly one Hoist object and run the "
            "write-test script again.\n\nSelected Hoists: {}".format(len(handles)))
        return False

    handle = handles[0]
    record_name, old_fields = get_parametric_info(vs_module, handle)
    if record_name != "BrxHoist":
        vs_module.AlrtDialog("The selected object is not a BrxHoist.")
        return False

    explanation = "\n".join(
        "{} = {}".format(field, label) for field, _, label in FIELD_PROBES)
    if not vs_module.YNDialog(
            "RigCalc isolated write test\n\n"
            "This writes four test values to the selected Hoist:\n\n{}\n\n"
            "The operation can be reverted with Undo. Continue?".format(explanation)):
        return False

    vs_module.NameUndoEvent("RigCalc Hoist field write test")
    for field, raw_value, _ in FIELD_PROBES:
        vs_module.SetRField(handle, "BrxHoist", field, raw_value)
    vs_module.ResetObject(handle)

    _, new_fields = get_parametric_info(vs_module, handle)
    lines = []
    for field, _, label in FIELD_PROBES:
        lines.append("{}: {} -> {} ({})".format(
            field, old_fields.get(field, ""), new_fields.get(field, ""), label))
    vs_module.AlrtDialog(
        "RigCalc write test completed.\n\n{}\n\n"
        "Report which number appears in which Vectorworks UI field."
        .format("\n".join(lines)))
    return True
