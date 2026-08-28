import unittest

from rigcalc.model import Point3D
from rigcalc.topology.geometry import point_to_segment


class GeometryTests(unittest.TestCase):
    def test_point_projects_to_segment(self):
        distance, fraction, x, y, z = point_to_segment(
            Point3D(500, 100), Point3D(0, 0), Point3D(1000, 0))
        self.assertAlmostEqual(distance, 100)
        self.assertAlmostEqual(fraction, 0.5)
        self.assertEqual((x, y, z), (500, 0, 0))

    def test_point_projects_to_sloped_segment_in_3d(self):
        distance, fraction, x, y, z = point_to_segment(
            Point3D(1500, 100, 1500),
            Point3D(0, 0, 0), Point3D(3000, 0, 3000))
        self.assertAlmostEqual(distance, 100)
        self.assertAlmostEqual(fraction, 0.5)
        self.assertEqual((x, y, z), (1500, 0, 1500))


if __name__ == "__main__":
    unittest.main()
