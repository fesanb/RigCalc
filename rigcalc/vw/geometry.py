from rigcalc.model.geometry import BoundingBox, Point3D


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


def center_point(vs, handle):
    """3D centre of the object's geometry as (x, y, z), or None.

    ``Get3DCntr`` returns ``((x, y), z)``.  For a truss of symmetric section
    this is the midpoint of its centreline in world coordinates, unlike the
    symbol insertion point, which lies at the bottom of the start face.
    """
    try:
        plan, z = vs.Get3DCntr(handle)
        x, y = float(plan[0]), float(plan[1])
        return x, y, float(z)
    except Exception:
        return None


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
