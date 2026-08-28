from dataclasses import dataclass, field
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
    cross_section_id: str = ""
    mechanical_section: Optional[MechanicalSection] = None
    cross_section_issues: list = field(default_factory=list)
    vw_truss_system: str = ""
    vw_truss_line: str = ""
    source_position_name: str = ""
    vw_connections: Dict[str, str] = field(default_factory=dict)
    source_ref: Any = field(default=None, repr=False, compare=False)

    @property
    def is_line(self):
        return self.item_type == "Line" and self.start is not None and self.end is not None

    @property
    def geometric_length_mm(self):
        if not self.is_line:
            return 0.0
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        dz = self.end.z - self.start.z
        return (dx * dx + dy * dy + dz * dz) ** 0.5
