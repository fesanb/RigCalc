def safe_float(value, default=None):
    if value is None:
        return default
    try:
        text = str(value).strip().replace(",", ".")
        if not text:
            return default
        for unit in (" kg", "kg", " mm", "mm", " kN", "kN", " N", "N", "°"):
            text = text.replace(unit, "")
        return float(text)
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
