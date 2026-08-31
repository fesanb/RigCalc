from math import isfinite


def safe_float(value, default=None):
    if value is None:
        return default
    try:
        text = str(value).strip().replace(",", ".")
        if not text:
            return default
        for unit in (" kg", "kg", " mm", "mm", " kN", "kN", " N", "N", "°"):
            text = text.replace(unit, "")
        parsed = float(text)
        return parsed if isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def get_record_fields(vs, handle, record):
    result = {}
    if not record:
        return result
    try:
        record_name, count = vs.GetName(record), vs.NumFields(record)
    except Exception:
        return result
    for index in range(1, count + 1):
        try:
            field_name = vs.GetFldName(record, index)
            if field_name:
                result[field_name] = vs.GetRField(handle, record_name, field_name)
        except Exception:
            pass
    return result


def get_parametric_info(vs, handle):
    try:
        record = vs.GetParametricRecord(handle)
        if not record:
            return None, {}
        return vs.GetName(record), get_record_fields(vs, handle, record)
    except Exception:
        return None, {}


def get_all_record_info(vs, handle):
    """Return every record attached to an object, including its PIO record."""
    result = []
    try:
        count = vs.NumRecords(handle)
    except Exception:
        count = 0
    for index in range(1, count + 1):
        try:
            record = vs.GetRecord(handle, index)
            record_name = vs.GetName(record) if record else None
        except Exception:
            continue
        if record_name:
            result.append({
                "name": record_name,
                "fields": get_record_fields(vs, handle, record),
            })
    return result
