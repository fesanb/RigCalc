import unittest

from rigcalc.model import Point3D, TrussSegment
from rigcalc.topology.connections import detect_connections


def line(identifier, start, end):
    return TrussSegment(identifier, identifier, "Line", start,
                        ((end.x-start.x)**2 + (end.y-start.y)**2)**0.5,
                        start, end)


class ConnectionTests(unittest.TestCase):
    def test_infers_small_overlap(self):
        connections = detect_connections([
            line("A", Point3D(0, 0), Point3D(3000, 0)),
            line("B", Point3D(2761, 0), Point3D(4261, 0)),
        ])
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0].confidence, "INFERRED")
        self.assertAlmostEqual(connections[0].distance_mm, 239)

    def test_connects_matching_3d_endpoints(self):
        connections = detect_connections([
            line("A", Point3D(0, 0, 0), Point3D(1000, 0, 2000)),
            line("B", Point3D(1000, 0, 2000), Point3D(2000, 0, 4000)),
        ])
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0].confidence, "EXACT")

    def test_does_not_connect_xy_match_at_different_elevations(self):
        connections = detect_connections([
            line("A", Point3D(0, 0, 0), Point3D(3000, 0, 0)),
            line("B", Point3D(3000, 0, 1000), Point3D(6000, 0, 1000)),
        ])
        self.assertEqual(connections, [])


if __name__ == "__main__":
    unittest.main()
