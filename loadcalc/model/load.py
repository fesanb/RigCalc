from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .geometry import Point3D


@dataclass
class PointLoad:
    id: str
    name: str
    position: Point3D
    record_type: str
    weight_kg: Optional[float] = None
    weight_raw: Any = None
    raw_fields: Dict[str, str] = field(default_factory=dict, repr=False)
    source_ref: Any = field(default=None, repr=False)
