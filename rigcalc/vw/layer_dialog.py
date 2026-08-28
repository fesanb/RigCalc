"""Calculation-scope dialog for selecting relevant Vectorworks layers."""

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
        item.get("layer_name", "")
        for item in inventory
        if item.get("layer_name") and item.get("parametric_record") in RELEVANT_RECORDS
    }, key=str.casefold)


def _read_previous(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return set(json.load(stream).get("included_layers", []))
    except (OSError, ValueError, TypeError):
        return set()


def _write_selection(path, selected):
    try:
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"included_layers": selected}, stream, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _checkbox_state(value):
    """Normalize Python-wrapper variants returning bool or (success, bool)."""
    if isinstance(value, (tuple, list)):
        return bool(value[-1]) if value else False
    return bool(value)


def choose_calculation_layers(vs, inventory, output_dir):
    layers = candidate_layers(inventory)
    if not layers:
        vs.AlrtDialog("RigCalc found no layers containing calculation-relevant objects.")
        return None

    selection_path = os.path.join(output_dir, "rigcalc_layer_selection.json")
    previous = _read_previous(selection_path)
    dialog = vs.CreateLayout(
        "RigCalc - Velg beregningsomfang", False,
        "Beregn valgte lag", "Avbryt")
    heading_id, info_id, disclaimer_id, first_checkbox_id = 4, 5, 6, 10
    vs.CreateStaticText(
        dialog, heading_id,
        "1. Velg lagene som skal inngå i beregningen", 72,
    )
    vs.CreateStaticText(
        dialog, info_id,
        "Huk av lag med hengende konstruksjon og utstyr. Ikke velg lag for "
        "utstyr på gulv, lager, venue eller presentasjon.",
        72,
    )
    vs.CreateStaticText(
        dialog, disclaimer_id,
        "Viktig: RigCalc er eksperimentelt. Resultatet må kontrolleres av "
        "kvalifisert personell og kan ikke brukes som eneste grunnlag for "
        "sikkerhetskritiske riggbeslutninger.",
        72,
    )
    vs.SetFirstLayoutItem(dialog, heading_id)
    vs.SetBelowItem(dialog, heading_id, info_id, 0, 1)
    for index, layer_name in enumerate(layers):
        item_id = first_checkbox_id + index
        vs.CreateCheckBox(dialog, item_id, layer_name)
        anchor = info_id if index == 0 else item_id - 1
        vs.SetBelowItem(dialog, anchor, item_id, 0, 0)
    vs.SetBelowItem(
        dialog, first_checkbox_id + len(layers) - 1,
        disclaimer_id, 0, 2,
    )

    result = {"selected": []}

    def handler(item, data):
        if item == 12255:  # SetupDialogC
            for index, layer_name in enumerate(layers):
                vs.SetBooleanItem(
                    dialog, first_checkbox_id + index,
                    layer_name in previous,
                )
        elif item == 1:
            # Read controls before Vectorworks destroys the closed dialog.
            result["selected"] = [
                layer_name for index, layer_name in enumerate(layers)
                if _checkbox_state(vs.GetBooleanItem(
                    dialog, first_checkbox_id + index))
            ]

    if vs.RunLayoutDialog(dialog, handler) != 1:
        return None
    selected = result["selected"]
    if not selected:
        vs.AlrtDialog(
            "Ingen beregningslag ble valgt.\n\n"
            "RigCalc stoppet uten å erstatte rapportene."
        )
        return None
    _write_selection(selection_path, selected)
    return selected
