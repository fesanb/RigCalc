import unittest

from rigcalc.model import DocumentModel, Point3D, Support, TrussSegment
from rigcalc.topology import build_constructions


class AttachmentTests(unittest.TestCase):
    def test_support_projects_to_station(self):
        start, end = Point3D(0, 0), Point3D(9000, 0)
        truss = TrussSegment("T1", "", "Line", start, 9000, start, end)
        support = Support("H1", "H001", Point3D(644, 0))
        construction = build_constructions(DocumentModel([truss], [support]))[0]
        self.assertAlmostEqual(construction.supports[0].attachment.global_station_mm, 644)


if __name__ == "__main__":
    unittest.main()
