import unittest

from rigcalc.model import DocumentModel, Point3D, TrussSegment
from rigcalc.topology import build_constructions


def line(identifier, start_x, end_x):
    start, end = Point3D(start_x, 0), Point3D(end_x, 0)
    return TrussSegment(identifier, identifier, "Line", start,
                        abs(end_x-start_x), start, end,
                        z_rotation_deg=0 if end_x >= start_x else 180)


class StationingTests(unittest.TestCase):
    def test_station_zero_is_smallest_x_independent_of_object_direction(self):
        document = DocumentModel(trusses=[line("B", 4500, 3000), line("A", 3000, 0)])
        construction = build_constructions(document)[0]
        self.assertEqual(construction.ordered_truss_ids, ["A", "B"])
        self.assertEqual(construction.station_map["A"].direction, "reverse")
        self.assertAlmostEqual(construction.structural_span_mm, 4500)

    def test_reports_nominal_and_physical_overlap_span_separately(self):
        document = DocumentModel(trusses=[line("A", 0, 3000), line("B", 2761, 4261)])
        construction = build_constructions(document)[0]
        self.assertAlmostEqual(construction.nominal_truss_length_mm, 4500)
        # This assertion documents the required geometry milestone.
        self.assertAlmostEqual(construction.structural_span_mm, 4261)


if __name__ == "__main__":
    unittest.main()
