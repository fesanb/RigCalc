from dataclasses import dataclass
from typing import Any

from .geometry import Point3D


@dataclass
class Support:
    id: str
    name: str
    position: Point3D
    hoist_id: str = ""
    capacity_raw: str = ""
    vw_truss_system: str = ""
    source_ref: Any = None
