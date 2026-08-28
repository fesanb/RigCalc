import os
import unittest

from rigcalc.model import Point3D, TrussSegment
from rigcalc.solver.cross_sections import (assign_cross_sections,
                                           load_section_library)


ROOT = os.path.join(os.path.dirname(__file__), "fixtures", "cross_sections")


class CrossSectionTests(unittest.TestCase):
    def test_loads_and_converts_vectorworks_xml_to_si(self):
        section = load_section_library([ROOT])["TEST-TRUSS"]
        self.assertAlmostEqual(section.area_m2, 0.00125)
        self.assertAlmostEqual(section.shear_area_y_m2, 0.00055)
        self.assertAlmostEqual(section.shear_area_z_m2, 0.00045)
        self.assertAlmostEqual(section.ixx_m4, 1.0e-6)
        self.assertAlmostEqual(section.iyy_m4, 2.0e-6)
        self.assertAlmostEqual(section.izz_m4, 3.0e-6)
        self.assertEqual(section.elastic_modulus_pa, 70.0e9)
        self.assertEqual(section.shear_modulus_pa, 26.5e9)
        self.assertEqual(section.max_axial_n, 30000)
        self.assertEqual(section.max_shear_y_n, 12000)
        self.assertEqual(section.max_shear_z_n, 10000)
        self.assertEqual(section.max_torsion_nm, 2000)
        self.assertEqual(section.max_moment_y_nm, 8000)
        self.assertEqual(section.max_moment_z_nm, 7000)

    def test_assigns_by_truss_cross_section_identifier(self):
        truss = TrussSegment(
            "T1", "", "Line", Point3D(0, 0),
            cross_section_id="TEST-TRUSS")
        assign_cross_sections([truss], [ROOT])
        self.assertEqual(truss.mechanical_section.identifier, "TEST-TRUSS")
        self.assertEqual(truss.cross_section_issues, [])

    def test_missing_identifier_is_explicit(self):
        truss = TrussSegment("T1", "", "Line", Point3D(0, 0))
        assign_cross_sections([truss], [ROOT])
        self.assertEqual(truss.cross_section_issues,
                         ["cross_section_id_missing"])


if __name__ == "__main__":
    unittest.main()
