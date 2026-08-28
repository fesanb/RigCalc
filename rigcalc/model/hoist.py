from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .geometry import Point3D


@dataclass
class Support:
    id: str
    name: str
    position: Point3D
    hoist_id: str = ""
    capacity_raw: str = ""
    vw_truss_system: str = ""
    vw_truss_system_top: str = ""
    weight_with_chain_kg: float = 0.0
    capacity_kg: float = 0.0
    transfer_target_construction_id: str = ""
    transfer_target_station_mm: Optional[float] = None
    is_structural_link: bool = False
    # Preserve the evidence used to derive the physical rigging connection.
    # These values are diagnostic for now; the solver still uses ``position``.
    object_position: Optional[Point3D] = None
    geometry_fields: Dict[str, str] = field(default_factory=dict)
    support_kind: str = "hoist"
    transfer_target_position: Optional[Point3D] = None
    source_ref: Any = None
