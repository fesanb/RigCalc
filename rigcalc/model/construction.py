from dataclasses import dataclass, field
from typing import List, Optional

from .hoist import Support
from .load import DistributedLoad, PointLoad, StructuralLink
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
    projected_z: Optional[float] = None
    method: str = "geometry_sphere"
    confidence: str = "INFERRED"
    carrier_clearance_mm: Optional[float] = None
    end_global_station_mm: Optional[float] = None


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
    name: str = ""
    source_system_names: List[str] = field(default_factory=list)
    ordered_truss_ids: List[str] = field(default_factory=list)
    station_map: dict = field(default_factory=dict)
    supports: List[AttachedObject] = field(default_factory=list)
    point_loads: List[AttachedObject] = field(default_factory=list)
    distributed_loads: List[AttachedObject] = field(default_factory=list)
    nominal_truss_length_mm: float = 0.0
    structural_span_mm: Optional[float] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def label(self):
        return self.name or self.id


@dataclass
class DocumentModel:
    trusses: List[TrussSegment] = field(default_factory=list)
    supports: List[Support] = field(default_factory=list)
    point_loads: List[PointLoad] = field(default_factory=list)
    distributed_loads: List[DistributedLoad] = field(default_factory=list)
    unassigned_supports: List[Support] = field(default_factory=list)
    unassigned_support_diagnostics: dict = field(default_factory=dict)
    unassigned_attachment_diagnostics: dict = field(default_factory=dict)
    unassigned_point_loads: List[PointLoad] = field(default_factory=list)
    unassigned_distributed_loads: List[DistributedLoad] = field(default_factory=list)
    structural_links: List[StructuralLink] = field(default_factory=list)
    suppressed_point_loads: List[PointLoad] = field(default_factory=list)
    ignored_record_types: List[str] = field(default_factory=list)
