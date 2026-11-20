"""Multi-leg bridles and the house rigging points their legs hang from."""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from .geometry import Point3D


@dataclass
class HouseRiggingPoint:
    id: str
    position: Point3D
    object_uuid: str = ""
    # Vectorworks/Braceworks values in N, kept for comparison only.
    vw_force_n: Optional[tuple] = None
    max_force_n: Optional[tuple] = None
    source_ref: Any = field(default=None, repr=False, compare=False)


@dataclass
class BridleLeg:
    number: int
    length_mm: float
    trim_mm: float
    angle_deg: Optional[float] = None
    vw_force_n: Optional[float] = None
    max_force_n: Optional[float] = None


@dataclass
class Bridle:
    id: str
    name: str
    index: str
    bridle_type: str
    apex: Point3D
    connected_hoist_uuid: str = ""
    weight_kg: float = 0.0
    weight_raw_kg: float = 0.0
    legs: List[BridleLeg] = field(default_factory=list)
    # The down leg is the hoist hanging from the apex (N in Vectorworks).
    down_leg_max_force_n: Optional[float] = None
    object_uuid: str = ""
    source_ref: Any = field(default=None, repr=False, compare=False)
