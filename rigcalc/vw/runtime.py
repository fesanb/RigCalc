from rigcalc.topology import build_constructions

from .scanner import scan_document
from .writer import write_reports


def run(vs_module=None):
    if vs_module is None:
        import vs as vs_module
    document = scan_document(vs_module)
    constructions = build_constructions(document)
    return write_reports(vs_module, document, constructions)
