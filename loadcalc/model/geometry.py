from dataclasses import dataclass


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class BoundingBox:
    first: Point3D
    second: Point3D
