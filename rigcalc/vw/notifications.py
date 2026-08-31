"""Create and reconcile RigCalc-owned notification markers in Vectorworks."""

from rigcalc.notifications import (DEFLECTION_NOTIFICATION_CLASS,
                                   INTERNAL_NOTIFICATION_CLASS,
                                   LOAD_NOTIFICATION_CLASS)


BASE_CLASS = "RigCalc"
OBJECT_NAME_PREFIX = "__RigCalcNotification__"
MARKER_OFFSET_MM = 500.0
RED = (52428, 0, 0)
ORANGE = (65535, 32768, 0)
BLUE = (0, 19660, 52428)
WHITE = (65535, 65535, 65535)
NOTIFICATION_CLASSES = (
    LOAD_NOTIFICATION_CLASS,
    DEFLECTION_NOTIFICATION_CLASS,
    INTERNAL_NOTIFICATION_CLASS,
)
CLASS_FILL_COLORS = {
    LOAD_NOTIFICATION_CLASS: RED,
    DEFLECTION_NOTIFICATION_CLASS: ORANGE,
    INTERNAL_NOTIFICATION_CLASS: BLUE,
}
TEXT_HAS_TIGHT_FILL_SELECTOR = 684


def _class_exists(vs, name):
    """Return whether *name* already occurs in the document class list."""
    return any(vs.ClassList(index) == name
               for index in range(1, vs.ClassNum() + 1))


def _ensure_classes(vs):
    old_class = vs.ActiveClass() if hasattr(vs, "ActiveClass") else None
    # NameClass creates a class when its argument does not already exist.
    # Vectorworks may return the active class as a numeric index (including a
    # float-like bridge value), so resolve it *only* to a known class name
    # before using NameClass to restore the active class.  This must fail
    # closed: never feed an unverified value back into NameClass.
    old_class_name = None
    if isinstance(old_class, str) and _class_exists(vs, old_class):
        old_class_name = old_class
    else:
        try:
            candidate = vs.ClassList(int(old_class))
            if candidate and _class_exists(vs, candidate):
                old_class_name = candidate
        except (TypeError, ValueError, OverflowError):
            pass
    try:
        for name in (BASE_CLASS,) + NOTIFICATION_CLASSES:
            # GetObject does not reliably return a class definition in all
            # Vectorworks contexts, so look in the document's class table.
            if not _class_exists(vs, name):
                vs.NameClass(name)
                if name in CLASS_FILL_COLORS:
                    color = CLASS_FILL_COLORS[name]
                    vs.SetClFillFore(name, color)
                    vs.SetClFillBack(name, color)
                    vs.SetClFPat(name, 1)
                    vs.SetClPenFore(name, WHITE)
                    vs.SetClPenBack(name, WHITE)
                    vs.SetClLSN(name, 2)
                    vs.SetClLW(name, 5)
                    vs.SetClOpacity(name, 100)
                    vs.SetClUseGraphic(name, True)
    finally:
        if old_class_name:
            vs.NameClass(old_class_name)


def _owned_marker_handles(vs):
    handles = []
    seen = set()

    def collect(handle):
        name = vs.GetName(handle) or ""
        if name.startswith(OBJECT_NAME_PREFIX) and handle not in seen:
            seen.add(handle)
            handles.append(handle)

    for class_name in NOTIFICATION_CLASSES:
        vs.ForEachObject(collect, "((C='{}'))".format(class_name))
    return handles


def _safe_object_name(notification_id):
    value = "".join(
        character if character.isalnum() or character in "_-" else "_"
        for character in notification_id)
    return OBJECT_NAME_PREFIX + value


def _construction_position(construction, station_mm):
    for truss in construction.truss_segments:
        span = construction.station_map.get(truss.id)
        if span is None or truss.start is None or truss.end is None:
            continue
        low = min(span.start_station_mm, span.end_station_mm)
        high = max(span.start_station_mm, span.end_station_mm)
        if not low-1.0e-6 <= station_mm <= high+1.0e-6:
            continue
        length = high-low
        fraction = 0.0 if length <= 1.0e-6 else (station_mm-low)/length
        start, end = truss.start, truss.end
        if span.direction != "forward":
            start, end = end, start
        return ((start.x + fraction*(end.x-start.x),
                 start.y + fraction*(end.y-start.y)), truss.source_ref)
    return None, None


def _notification_position(document, constructions, notification):
    support_id = notification.get("support_id")
    if support_id:
        support = next((item for item in document.supports
                        if item.id == support_id), None)
        if support is not None:
            return (support.position.x, support.position.y), support.source_ref
    construction = next((item for item in constructions
                         if item.id == notification.get("construction_id")),
                        None)
    station = notification.get("source_station_mm")
    if construction is not None and station is not None:
        return _construction_position(construction, station)
    return None, None


def write_notification_markers(vs, document, constructions, notifications):
    """Replace only markers explicitly named as RigCalc-owned objects."""
    _ensure_classes(vs)
    old_markers = _owned_marker_handles(vs)
    created = []
    vs.NameUndoEvent("RigCalc notifications")
    for handle in old_markers:
        vs.DelObject(handle)
    for notification in notifications:
        position, source_ref = _notification_position(
            document, constructions, notification)
        if position is None:
            continue
        x = position[0] + MARKER_OFFSET_MM
        y = position[1] + MARKER_OFFSET_MM
        vs.TextOrigin(x, y)
        vs.CreateText(notification["message"])
        handle = vs.LNewObj()
        if not handle:
            continue
        vs.SetClass(handle, notification["class_name"])
        vs.SetFillColorByClass(handle)
        vs.SetFPatByClass(handle)
        vs.SetPenColorByClass(handle)
        # SetTextWidth turns wrapping on, so never call it for notifications.
        # CreateText is unwrapped by default, but state it explicitly because
        # document/tool state can otherwise leak into newly created text.
        vs.SetTextWrap(handle, False)
        vs.SetObjectVariableBoolean(
            handle, TEXT_HAS_TIGHT_FILL_SELECTOR, False)
        vs.SetName(handle, _safe_object_name(notification["id"]))
        # New objects are born on the active layer. Move the marker alongside
        # its source object when the API/runtime permits it.
        if source_ref is not None and hasattr(vs, "SetParent"):
            parent = vs.GetParent(source_ref)
            if parent:
                vs.SetParent(handle, parent)
        created.append({
            "notification_id": notification["id"],
            "support_id": notification.get("support_id", ""),
            "construction_id": notification.get("construction_id", ""),
            "status": "written",
        })
    return {
        "status": "written",
        "removed_count": len(old_markers),
        "written_count": len(created),
        "items": created,
    }
