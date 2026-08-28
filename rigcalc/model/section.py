from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MechanicalSection:
    """Normalized SI properties used by the mechanical solver."""

    identifier: str
    name: str
    manufacturer: str
    material_name: str
    area_m2: Optional[float]
    shear_area_y_m2: Optional[float]
    shear_area_z_m2: Optional[float]
    ixx_m4: Optional[float]
    iyy_m4: Optional[float]
    izz_m4: Optional[float]
    elastic_modulus_pa: Optional[float]
    shear_modulus_pa: Optional[float]
    poisson_ratio: Optional[float]
    density_kg_m3: Optional[float]
    source_path: str
    max_axial_n: Optional[float] = None
    max_shear_y_n: Optional[float] = None
    max_shear_z_n: Optional[float] = None
    max_torsion_nm: Optional[float] = None
    max_moment_y_nm: Optional[float] = None
    max_moment_z_nm: Optional[float] = None
    material_source_path: str = ""
    issues: List[str] = field(default_factory=list)
