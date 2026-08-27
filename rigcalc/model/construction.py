from dataclasses import dataclass, field
from typing import List, Optional

from .hoist import Support
from .load import PointLoad
from .truss import TrussSegment


@dataclass
class Connection:
    a: str
    b: str
    a_port: str
    b_port: str
    method: str
    distance_mm: float
    confidence: str
    longitudinal_error_mm: float = 0.0


@dataclass
class StationRange:
    start_station_mm: float
    end_station_mm: float
    direction: str


@dataclass
class Attachment:
    truss_id: str
    truss_name: str
    distance_from_truss_axis_mm: float
    local_position_from_truss_start_mm: float
    global_station_mm: Optional[float]
    projected_x: float
    projected_y: float
    warning: bool = False


@dataclass
class AttachedObject:
    item: object
    attachment: Attachment


@dataclass
class Construction:
    id: str
    truss_segments: List[TrussSegment]
    connections: List[Connection]
    stationing: str
    ordered_truss_ids: List[str] = field(default_factory=list)
    station_map: dict = field(default_factory=dict)
    supports: List[AttachedObject] = field(default_factory=list)
    point_loads: List[AttachedObject] = field(default_factory=list)
    nominal_truss_length_mm: float = 0.0
    structural_span_mm: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class DocumentModel:
    trusses: List[TrussSegment] = field(default_factory=list)
    supports: List[Support] = field(default_factory=list)
    point_loads: List[PointLoad] = field(default_factory=list)
    ignored_record_types: List[str] = field(default_factory=list)
