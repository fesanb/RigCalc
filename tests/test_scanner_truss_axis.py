"""Truss centreline from the 3D centre (Vectorworks test file regression).

The symbol insertion point lies at the bottom of the start face.  Building
the axis from it put vertical trusses half a length too high and half a
section off-axis, and inclined trusses half their rise too high, so they no
longer reached their corner blocks or hoists.
"""

import unittest

from rigcalc.vw.scanner import _parse_truss


class AxisVS:
    def __init__(self, insertion, center, elevation, rotation=0.0):
        self.insertion, self.center = insertion, center
        self.elevation, self.rotation = elevation, rotation

    def GetSymLoc(self, handle):
        return self.insertion

    def Get3DCntr(self, handle):
        return (self.center[0], self.center[1]), self.center[2]

    def Get3DOrientation(self, handle):
        return True, 0.0, self.elevation, self.rotation, False

    def GetBBox(self, handle):
        return (0.0, 0.0), (1.0, 1.0)


class TrussAxisTests(unittest.TestCase):
    def parse(self, vs, length="2000"):
        return _parse_truss(vs, "h", "T1", {"ItemType": "Line",
                                            "Length": length})

    def test_vertical_truss_spans_its_true_height_on_the_centreline(self):
        # Lower box centre at z=-2144, upper at z=144; the insertion point is
        # 143.5 mm off the axis at the bottom of the section.
        vs = AxisVS((124864.0, 17940.0), (124720.5, 17940.0, -1000.0), -90.0)
        truss = self.parse(vs)
        self.assertAlmostEqual(truss.start.z, -2000.0)
        self.assertAlmostEqual(truss.end.z, 0.0)
        self.assertAlmostEqual(truss.start.x, 124720.5)
        self.assertAlmostEqual(truss.end.x, 124720.5)

    def test_inclined_truss_is_centred_on_its_3d_centre(self):
        vs = AxisVS((0.0, 0.0), (2598.076211, 0.0, 1500.0), -30.0)
        truss = self.parse(vs, "6000")
        self.assertAlmostEqual(truss.start.z, 0.0, places=2)
        self.assertAlmostEqual(truss.end.z, 3000.0, places=2)
        self.assertAlmostEqual(truss.start.x, 0.0, places=2)
        self.assertAlmostEqual(truss.end.x, 5196.152422, places=3)

    def test_level_truss_is_unchanged(self):
        vs = AxisVS((0.0, 6775.0), (1500.0, 6775.0, 145.0), 0.0)
        truss = self.parse(vs, "3000")
        self.assertAlmostEqual(truss.start.x, 0.0)
        self.assertAlmostEqual(truss.end.x, 3000.0)
        self.assertAlmostEqual(truss.start.z, 145.0)
        self.assertAlmostEqual(truss.end.z, 145.0)


if __name__ == "__main__":
    unittest.main()
