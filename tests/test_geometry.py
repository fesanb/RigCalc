import unittest

from loadcalc.model import Point3D
from loadcalc.topology.geometry import point_to_segment


class GeometryTests(unittest.TestCase):
    def test_point_projects_to_segment(self):
        distance, fraction, x, y = point_to_segment(
            Point3D(500, 100), Point3D(0, 0), Point3D(1000, 0))
        self.assertAlmostEqual(distance, 100)
        self.assertAlmostEqual(fraction, 0.5)
        self.assertEqual((x, y), (500, 0))


if __name__ == "__main__":
    unittest.main()
