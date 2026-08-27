import json
from dataclasses import fields, is_dataclass


def _clean(value):
    if is_dataclass(value):
        # Do not use dataclasses.asdict(): it deep-copies opaque Vectorworks
        # handles before we get a chance to exclude source_ref.
        return {
            field.name: _clean(getattr(value, field.name))
            for field in fields(value)
            if field.name not in ("source_ref", "raw_fields")
        }
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items() if key not in ("source_ref", "raw_fields")}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if not isinstance(value, (str, int, float, bool, type(None))):
        return repr(value)
    return value


def write_json_report(path, document, constructions, settings):
    data = {"settings": settings, "document": _clean(document), "constructions": _clean(constructions)}
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
