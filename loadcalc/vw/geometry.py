from loadcalc.model.geometry import BoundingBox, Point3D


def symbol_location(vs, handle):
    try:
        point = vs.GetSymLoc(handle)
        return Point3D(float(point[0]), float(point[1]), 0.0)
    except Exception:
        return None


def center_z(vs, handle):
    try:
        return float(vs.Get3DCntr(handle)[1])
    except Exception:
        return 0.0


def z_rotation(vs, handle):
    try:
        orientation = vs.Get3DOrientation(handle)
        return float(orientation[3]) if orientation[0] else 0.0
    except Exception:
        return 0.0


def bounding_box(vs, handle):
    try:
        first, second = vs.GetBBox(handle)
        return BoundingBox(Point3D(float(first[0]), float(first[1])), Point3D(float(second[0]), float(second[1])))
    except Exception:
        return None
