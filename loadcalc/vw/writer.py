import os

from loadcalc import config
from loadcalc.report import make_text_report, write_json_report


def report_output_directory():
    loadcalc_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(loadcalc_root, config.OUTPUT_DIRECTORY_NAME)


def write_reports(vs, document, constructions):
    output_dir = report_output_directory()
    os.makedirs(output_dir, exist_ok=True)
    text_path = os.path.join(output_dir, config.REPORT_BASENAME + ".txt")
    json_path = os.path.join(output_dir, config.REPORT_BASENAME + ".json")
    with open(text_path, "w", encoding="utf-8") as stream:
        stream.write(make_text_report(document, constructions))
    settings = {
        "endpoint_tolerance_mm": config.ENDPOINT_TOLERANCE_MM,
        "collinear_longitudinal_tolerance_mm": config.COLLINEAR_LONGITUDINAL_TOLERANCE_MM,
        "collinear_lateral_tolerance_mm": config.COLLINEAR_LATERAL_TOLERANCE_MM,
        "collinear_angle_tolerance_deg": config.COLLINEAR_ANGLE_TOLERANCE_DEG,
        "corner_tolerance_mm": config.CORNER_TOLERANCE_MM,
        "attachment_warning_distance_mm": config.ATTACHMENT_WARNING_DISTANCE_MM,
    }
    write_json_report(json_path, document, constructions, settings)
    try:
        os.startfile(text_path)
    except Exception:
        pass
    vs.AlrtDialog(
        "LoadCalc geometry analysis complete.\n\n"
        "Constructions: {}\nTruss: {}\nHoists: {}\nLoads: {}\n\n"
        "Reports: {}".format(len(constructions), len(document.trusses),
                             len(document.supports), len(document.point_loads), output_dir)
    )
    return text_path, json_path
