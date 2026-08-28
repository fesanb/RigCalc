import unittest

from rigcalc.model import (AttachedObject, Attachment, Construction, Point3D,
                           PointLoad, Support)
from rigcalc.solver.beam_statics import solve_two_support_beam


def attached_support(identifier, station):
    support = Support(identifier, "", Point3D(station, 0))
    attachment = Attachment("T", "", 0, station, station, station, 0)
    return AttachedObject(support, attachment)


class SignedReactionTests(unittest.TestCase):
    def test_negative_reaction_is_retained_without_issue(self):
        construction = Construction(
            "C", [], [], "open_chain",
            supports=[attached_support("H1", 0),
                      attached_support("H2", 1000)])
        loads = [{
            "source_id": "L", "source_type": "Load", "mass_kg": 100,
            "station_mm": 2000, "evidence": "test",
        }]
        result = solve_two_support_beam(construction, loads)
        self.assertAlmostEqual(result["reactions"][0]["reaction_mass_kg"], -100)
        self.assertAlmostEqual(result["reactions"][1]["reaction_mass_kg"], 200)
        self.assertEqual(result["issues"], [])


if __name__ == "__main__":
    unittest.main()
