from dataclasses import dataclass, field
from math import ceil, cos, radians, sin
from typing import Any, Dict, Optional

from .geometry import BoundingBox, Point3D
from .section import MechanicalSection


@dataclass
class TrussSegment:
    id: str
    name: str
    item_type: str
    position: Point3D
    nominal_length_mm: float = 0.0
    start: Optional[Point3D] = None
    end: Optional[Point3D] = None
    bbox: Optional[BoundingBox] = None
    z_rotation_deg: float = 0.0
    symbol: str = ""
    truss_type: str = ""
    corner_type: str = ""
    width_mm: float = 0.0
    height_mm: float = 0.0
    self_weight_kg: float = 0.0
    cable_load_kg_m: float = 0.0
    cross_section_id: str = ""
    mechanical_section: Optional[MechanicalSection] = None
    cross_section_issues: list = field(default_factory=list)
    vw_truss_system: str = ""
    vw_truss_line: str = ""
    source_position_name: str = ""
    vw_connections: Dict[str, str] = field(default_factory=dict)
    # Resolved centreline geometry of a curved (Circle) item:
    # {"center_x", "center_y", "z", "radius_mm", "start_angle_rad",
    #  "sweep_rad"}; sweep is signed (positive counter-clockwise).
    arc: Optional[Dict[str, float]] = None
    source_ref: Any = field(default=None, repr=False, compare=False)

    @property
    def is_line(self):
        return (self.item_type in ("Line", "Lighting Pipe") and
                self.start is not None and self.end is not None)

    @property
    def is_arc(self):
        return self.arc is not None

    @property
    def has_axis(self):
        """Whether the item has a resolved centreline (straight or curved)."""
        return self.is_line or self.is_arc

    def axis_points(self, maximum_angle_deg=1.0):
        """Centreline polyline from start to end (two points for a line)."""
        if self.is_line:
            return [self.start, self.end]
        if not self.is_arc:
            return []
        arc = self.arc
        count = max(1, int(ceil(abs(arc["sweep_rad"]) /
                                radians(maximum_angle_deg))))
        point_type = type(self.position)
        return [point_type(
            arc["center_x"]+arc["radius_mm"]*cos(
                arc["start_angle_rad"]+arc["sweep_rad"]*index/count),
            arc["center_y"]+arc["radius_mm"]*sin(
                arc["start_angle_rad"]+arc["sweep_rad"]*index/count),
            arc["z"]) for index in range(count+1)]

    @property
    def axis_length_mm(self):
        if self.is_arc:
            return abs(self.arc["sweep_rad"])*self.arc["radius_mm"]
        return self.geometric_length_mm

    @property
    def geometric_length_mm(self):
        if not self.is_line:
            return 0.0
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        dz = self.end.z - self.start.z
        return (dx * dx + dy * dy + dz * dz) ** 0.5
