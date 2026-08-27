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


if __name__ == "__main__":
    unittest.main()
