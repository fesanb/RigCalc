from rigcalc import config
from rigcalc.topology import build_constructions
from rigcalc.solver.cross_sections import assign_cross_sections

from .scanner import scan_document
from .inventory import scan_plugin_inventory
from .hanging_position import extract_hanging_position_trusses
from .hoist_ids import populate_missing_hoist_ids
from .layer_dialog import choose_calculation_layers
from .writer import report_output_directory, write_reports
from .progress import RigCalcCancelled, VWProgress


def run(vs_module=None):
    if vs_module is None:
        import vs as vs_module
    display = VWProgress(vs_module)

    def progress(action, value=None, message=None):
        if action == "start":
            display.start(value, message)
        elif action == "update":
            display.update(value, message)
        elif action == "close":
            display.close()
        else:
            display.pulse(message or "RigCalc arbeider")

    try:
        # The layer prompt only needs record and layer names. Keep this first
        # pass shallow so development diagnostics do not delay the prompt.
        inventory = scan_plugin_inventory(
            vs_module, progress=progress, detailed=False)
    except RigCalcCancelled:
        display.close()
        return None
    display.close()
    included_layers = choose_calculation_layers(
        vs_module, inventory, report_output_directory())
    if included_layers is None:
        return None
    display.begin_workflow(7)
    try:
        hoist_id_assignment = populate_missing_hoist_ids(vs_module)
        if config.WRITE_DEVELOPMENT_INVENTORY:
            # Capture complete PIO records only for the layers the user chose.
            # This is the object-parser evidence written to rigcalc_inventory.
            inventory = scan_plugin_inventory(
                vs_module, progress=progress, detailed=True,
                included_layers=included_layers)
        document = scan_document(
            vs_module, included_layers=included_layers, progress=progress)
        if config.WRITE_DEVELOPMENT_INVENTORY:
            hanging_position_inventory = [
                item for item in inventory
                if item.get("parametric_record") == "Light Position Obj" and
                item.get("layer_name") in included_layers]
        else:
            hanging_position_inventory = scan_plugin_inventory(
                vs_module, progress=progress, detailed=True,
                record_filter={"Light Position Obj"},
                included_layers=included_layers)
        document.trusses.extend(extract_hanging_position_trusses(
            hanging_position_inventory, included_layers))
        progress("start", 4, "Klargjør konstruksjoner 0/4")
        assign_cross_sections(document.trusses)
        progress("update", 2, "Bygger konstruksjonstopologi 2/4")
        constructions = build_constructions(document)
        progress("update", 4, "Konstruksjoner ferdige 4/4")
        return write_reports(
            vs_module, document, constructions, inventory,
            included_layers=included_layers, progress=progress,
            hoist_id_assignment=hoist_id_assignment,
        )
    except RigCalcCancelled:
        return None
    finally:
        display.close()
