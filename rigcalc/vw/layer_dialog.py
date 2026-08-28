"""Calculation-scope dialog for selecting layers and load settings."""

import json
import os


RELEVANT_RECORDS = {
    "TrussItem", "BrxHoist", "BrxCustomTrussCross", "BrxGenericWeight",
    "BrxDistributedWeight", "Lighting Device", "Speaker", "Speaker Array",
    "Video Screen", "Soft Goods", "Light Position Obj", "Lighting Pipe",
    "StructuralMember", "BridleObj",
}


def candidate_layers(inventory):
    return sorted({
        item.get("layer_name", "") for item in inventory
        if item.get("layer_name") and
        item.get("parametric_record") in RELEVANT_RECORDS
    }, key=str.casefold)


def _read_previous(path):
    return set(_read_previous_values(path).get("included_layers", []))


def _read_previous_values(path):
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
            return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_selection(path, selected, cable_load_kg_m=0.0,
                     safety_factor=1.0):
    try:
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({
                "included_layers": selected,
                "cable_load_kg_m": cable_load_kg_m,
                "safety_factor": safety_factor,
            }, stream, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _checkbox_state(value):
    """Normalize Python-wrapper variants returning bool or (success, bool)."""
    if isinstance(value, (tuple, list)):
        return bool(value[-1]) if value else False
    return bool(value)


def _display_number(value, default):
    try:
        return "{:.2f}".format(float(value)).replace(".", ",")
    except (TypeError, ValueError):
        return "{:.2f}".format(default).replace(".", ",")


def _parse_number(text, default, minimum=0.0, strictly_positive=False):
    try:
        value = float(str(text).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default
    if strictly_positive and value <= minimum:
        return default
    return max(minimum, value)


def choose_calculation_scope(vs, inventory, output_dir):
    layers = candidate_layers(inventory)
    if not layers:
        vs.AlrtDialog(
            "RigCalc found no layers containing calculation-relevant objects.")
        return None

    selection_path = os.path.join(output_dir, "rigcalc_layer_selection.json")
    previous_values = _read_previous_values(selection_path)
    previous_layers = set(previous_values.get("included_layers", []))
    dialog = vs.CreateLayout(
        "RigCalc | Calculation Setup", False,
        "Run Calculation", "Cancel")

    title_id, intro_id, layer_heading_id = 4, 5, 6
    cable_label_id, cable_edit_id = 7, 8
    factor_label_id, factor_edit_id = 9, 20
    load_heading_id, load_help_id = 21, 22
    review_heading_id, review_id, disclaimer_id = 23, 24, 25
    first_checkbox_id = 100

    vs.CreateStaticText(
        dialog, title_id, "RIGCALC  /  CALCULATION SETUP", 76)
    vs.CreateStaticText(
        dialog, intro_id,
        "Choose layers belonging to the suspended system. Exclude floor "
        "equipment, storage, venue geometry, and presentation layers.", 76)
    vs.CreateStaticText(
        dialog, layer_heading_id,
        "--- 1. CALCULATION LAYERS --------------------------------", 76)
    for index, layer_name in enumerate(layers):
        vs.CreateCheckBox(dialog, first_checkbox_id + index, layer_name)

    vs.CreateStaticText(
        dialog, load_heading_id,
        "--- 2. LOAD SETTINGS -------------------------------------", 76)
    vs.CreateStaticText(
        dialog, load_help_id,
        "Cable load follows the physical length of every line truss. The "
        "global safety factor is applied once to every scanned load.", 76)
    vs.CreateStaticText(dialog, cable_label_id, "Cable load (kg/m)", 24)
    vs.CreateEditText(dialog, cable_edit_id, "0,00", 10)
    vs.CreateStaticText(dialog, factor_label_id, "Safety factor", 24)
    vs.CreateEditText(dialog, factor_edit_id, "1,00", 10)
    vs.CreateStaticText(
        dialog, review_heading_id,
        "--- 3. REVIEW --------------------------------------------", 76)
    vs.CreateStaticText(
        dialog, review_id,
        "Settings are saved for the next run. Transferred reactions are not "
        "factored a second time.", 76)
    vs.CreateStaticText(
        dialog, disclaimer_id,
        "IMPORTANT: RigCalc is experimental. Results must be reviewed by a "
        "qualified person and must not be the sole basis for safety-critical "
        "rigging decisions.", 76)

    vs.SetFirstLayoutItem(dialog, title_id)
    vs.SetBelowItem(dialog, title_id, intro_id, 0, 1)
    vs.SetBelowItem(dialog, intro_id, layer_heading_id, 0, 2)
    for index in range(len(layers)):
        item_id = first_checkbox_id + index
        anchor = layer_heading_id if index == 0 else item_id - 1
        vs.SetBelowItem(dialog, anchor, item_id, 0, 0)
    last_layer_id = first_checkbox_id + len(layers) - 1
    vs.SetBelowItem(dialog, last_layer_id, load_heading_id, 0, 2)
    vs.SetBelowItem(dialog, load_heading_id, load_help_id, 0, 1)
    vs.SetBelowItem(dialog, load_help_id, cable_label_id, 2, 1)
    vs.SetRightItem(dialog, cable_label_id, cable_edit_id, 1, 0)
    vs.SetBelowItem(dialog, cable_label_id, factor_label_id, 0, 1)
    vs.SetRightItem(dialog, factor_label_id, factor_edit_id, 1, 0)
    vs.SetBelowItem(dialog, factor_label_id, review_heading_id, -2, 2)
    vs.SetBelowItem(dialog, review_heading_id, review_id, 0, 1)
    vs.SetBelowItem(dialog, review_id, disclaimer_id, 0, 2)

    result = {
        "selected": [], "cable_load_kg_m": 0.0, "safety_factor": 1.0}

    def handler(item, data):
        if item == 12255:  # SetupDialogC
            for index, layer_name in enumerate(layers):
                vs.SetBooleanItem(
                    dialog, first_checkbox_id + index,
                    layer_name in previous_layers)
            vs.SetItemText(
                dialog, cable_edit_id,
                _display_number(
                    previous_values.get("cable_load_kg_m"), 0.0))
            vs.SetItemText(
                dialog, factor_edit_id,
                _display_number(previous_values.get("safety_factor"), 1.0))
        elif item == 1:
            # Read controls before Vectorworks destroys the closed dialog.
            result["selected"] = [
                layer_name for index, layer_name in enumerate(layers)
                if _checkbox_state(vs.GetBooleanItem(
                    dialog, first_checkbox_id + index))]
            result["cable_load_kg_m"] = _parse_number(
                vs.GetItemText(dialog, cable_edit_id), 0.0)
            result["safety_factor"] = _parse_number(
                vs.GetItemText(dialog, factor_edit_id), 1.0,
                strictly_positive=True)

    if vs.RunLayoutDialog(dialog, handler) != 1:
        return None
    if not result["selected"]:
        vs.AlrtDialog(
            "No calculation layers were selected.\n\n"
            "RigCalc stopped without replacing existing reports.")
        return None
    _write_selection(
        selection_path, result["selected"], result["cable_load_kg_m"],
        result["safety_factor"])
    return result


def choose_calculation_layers(vs, inventory, output_dir):
    """Compatibility wrapper returning only the selected layer names."""
    scope = choose_calculation_scope(vs, inventory, output_dir)
    return None if scope is None else scope["selected"]
