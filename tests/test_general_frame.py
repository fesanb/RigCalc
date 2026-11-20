"""General 3D frame solver: hand-checkable benchmarks for every geometry.

Constructions are built through the real topology (connections, corners,
arcs, attachments).  Hoist/chain mass is never a truss load, so reactions
are the truss loads only.
"""

import unittest
from math import cos, pi, radians, sin

from rigcalc.model import (DocumentModel, Point3D, PointLoad, Support,
                           TrussSegment)
from rigcalc.model.geometry import BoundingBox
from rigcalc.solver.beam_statics import trace_construction_loads
from rigcalc.solver.general_frame import solve_general_frame
from rigcalc.solver.system import _solve_local
from rigcalc.topology import build_constructions
from tests.test_continuous_beam import section


def line(identifier, a, b, mass=0.0):
    length = sum((q-p)**2 for p, q in zip(a, b))**0.5
    return TrussSegment(identifier, "", "Line", Point3D(*a), length,
                        Point3D(*a), Point3D(*b), width_mm=290,
                        height_mm=290, self_weight_kg=mass,
                        mechanical_section=section())


def hoist(identifier, point):
    return Support(identifier, "", Point3D(*point), weight_with_chain_kg=10,
                   capacity_kg=1000, support_kind="hoist")


def load(identifier, point, mass):
    return PointLoad(identifier, "", Point3D(*point), "Load", mass)


def solve(trusses, hoists, loads=(), transferred=None):
    document = DocumentModel(trusses=trusses, supports=hoists,
                             point_loads=list(loads))
    constructions = build_constructions(document)
    assert len(constructions) == 1, [item.id for item in constructions]
    construction = constructions[0]
    extra = list(transferred or [])
    result = solve_general_frame(
        construction, trace_construction_loads(construction)+extra)
    return construction, result, document


def reactions(result):
    return {item["support_id"]: item["reaction_mass_kg"]
            for item in result["reactions"]}


class LevelChainAgreementTests(unittest.TestCase):
    def assert_matches_legacy(self, trusses, hoists, loads=()):
        construction, result, _ = solve(trusses, hoists, loads)
        legacy = _solve_local(construction,
                              trace_construction_loads(construction))
        self.assertTrue(result["writeback_eligible"])
        for item in legacy["reactions"]:
            self.assertAlmostEqual(reactions(result)[item["support_id"]],
                                   item["reaction_mass_kg"], delta=0.01)
        return result

    def test_two_supports_match_beam_statics(self):
        result = self.assert_matches_legacy(
            [line("T1", (0, 0, 0), (6000, 0, 0), 60)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (6000, 0, 0))],
            [load("P", (2000, 0, 0), 300)])
        self.assertAlmostEqual(reactions(result)["H1"], 230.0, delta=0.01)

    def test_three_supports_uniform_load_classic_values(self):
        result = self.assert_matches_legacy(
            [line("T1", (0, 0, 0), (10000, 0, 0), 100)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (5000, 0, 0)),
             hoist("H3", (10000, 0, 0))])
        self.assertAlmostEqual(reactions(result)["H2"], 62.5, delta=0.01)

    def test_overhang_releases_uplift_hoist(self):
        result = self.assert_matches_legacy(
            [line("T1", (0, 0, 0), (10000, 0, 0), 50)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (2000, 0, 0)),
             hoist("H3", (8000, 0, 0))], [load("P", (10000, 0, 0), 60)])
        by_id = {item["support_id"]: item for item in result["reactions"]}
        self.assertFalse(by_id["H2"]["support_active"])
        self.assertAlmostEqual(by_id["H1"]["reaction_mass_kg"], 3.75,
                               delta=0.01)
        self.assertAlmostEqual(by_id["H2"]["preliminary_high_hook_mass_kg"],
                               10.0)

    def test_rig_that_would_tip_reports_signed_result(self):
        _, result, _ = solve(
            [line("T1", (0, 0, 0), (10000, 0, 0), 50)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (2000, 0, 0)),
             hoist("H3", (8000, 0, 0))], [load("P", (10000, 0, 0), 120)])
        self.assertFalse(result["writeback_eligible"])
        self.assertIn("tension_only_active_set_no_feasible_solution",
                      result["issues"])
        self.assertLess(reactions(result)["H2"], -50.0)


class GeometryBenchmarkTests(unittest.TestCase):
    def test_square_frame_symmetric_load_quarter_each(self):
        frame = [line("S1", (0, 0, 0), (6000, 0, 0), 60),
                 line("S2", (6000, 0, 0), (6000, 6000, 0), 60),
                 line("S3", (6000, 6000, 0), (0, 6000, 0), 60),
                 line("S4", (0, 6000, 0), (0, 0, 0), 60)]
        corners = [(0, 0, 0), (6000, 0, 0), (6000, 6000, 0), (0, 6000, 0)]
        mids = [(3000, 0, 0), (6000, 3000, 0), (3000, 6000, 0), (0, 3000, 0)]
        construction, result, _ = solve(
            frame, [hoist("H%d" % i, p) for i, p in enumerate(corners)],
            [load("P%d" % i, p, 100) for i, p in enumerate(mids)])
        self.assertEqual(construction.stationing,
                         "closed_loop_arbitrary_origin")
        self.assertTrue(result["writeback_eligible"])
        for value in reactions(result).values():
            self.assertAlmostEqual(value, 160.0, delta=0.01)

    def test_l_frame_matches_three_point_statics(self):
        _, result, _ = solve(
            [line("A", (0, 0, 0), (6000, 0, 0), 60),
             line("B", (6000, 0, 0), (6000, 4000, 0), 40)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (6000, 0, 0)),
             hoist("H3", (6000, 4000, 0))],
            [load("P", (3000, 0, 0), 200), load("Q", (6000, 2000, 0), 200)])
        values = reactions(result)
        # Moments about the support lines x=6000 and y=0.
        self.assertAlmostEqual(values["H1"], 130.0, delta=0.01)
        self.assertAlmostEqual(values["H3"], 120.0, delta=0.01)
        self.assertAlmostEqual(values["H2"], 250.0, delta=0.01)
        self.assertTrue(result["writeback_eligible"])

    def test_t_junction_matches_three_point_statics(self):
        _, result, _ = solve(
            [line("A", (0, 0, 0), (4000, 0, 0), 40),
             line("B", (4000, 0, 0), (8000, 0, 0), 40),
             line("C", (4000, 0, 0), (4000, 3000, 0), 30)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (8000, 0, 0)),
             hoist("H3", (4000, 3000, 0))], [load("P", (4000, 3000, 0), 200)])
        values = reactions(result)
        self.assertAlmostEqual(values["H3"], 215.0, delta=0.01)
        self.assertAlmostEqual(values["H1"], 47.5, delta=0.01)
        self.assertTrue(result["writeback_eligible"])

    def test_vertical_truss_hanging_from_one_hoist(self):
        _, result, _ = solve([line("V", (0, 0, 3000), (0, 0, 0), 30)],
                             [hoist("H1", (0, 0, 3000))],
                             [load("P", (0, 0, 0), 200)])
        self.assertAlmostEqual(reactions(result)["H1"], 230.0, delta=0.01)
        self.assertTrue(result["writeback_eligible"])

    def test_inclined_truss_symmetric(self):
        _, result, _ = solve([line("I", (0, 0, 0), (6000, 0, 1000), 60)],
                             [hoist("H1", (0, 0, 0)),
                              hoist("H2", (6000, 0, 1000))],
                             [load("P", (3000, 0, 500), 200)])
        for value in reactions(result).values():
            self.assertAlmostEqual(value, 130.0, delta=0.01)
        self.assertTrue(result["writeback_eligible"])

    def test_corner_block_joins_members_at_axis_intersection(self):
        # Lines stop at the corner faces; the corner insertion point is at
        # one face, as for Spotlight C21 corners.
        corner = TrussSegment("K", "", "Corner", Point3D(6000, 0, 0),
                              self_weight_kg=10, width_mm=290, height_mm=290,
                              corner_type="L_Corner")
        _, result, _ = solve(
            [line("A", (0, 0, 0), (6000, 0, 0), 60), corner,
             line("B", (6250, 250, 0), (6250, 4250, 0), 40)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (5000, 0, 0)),
             hoist("H3", (6250, 4250, 0))])
        values = reactions(result)
        self.assertAlmostEqual(sum(values.values()), 110.0, delta=0.01)
        # Three supports: statics in plan with the corner mass at the axis
        # intersection (6250, 0) and B's centroid at y = 2250.
        r3 = 40.0*2250.0/4250.0
        r2 = (60.0*3000.0+10.0*6250.0+40.0*6250.0-r3*6250.0)/5000.0
        self.assertAlmostEqual(values["H3"], r3, delta=0.01)
        self.assertAlmostEqual(values["H2"], r2, delta=0.01)
        self.assertAlmostEqual(values["H1"], 110.0-r2-r3, delta=0.01)
        self.assertTrue(result["writeback_eligible"])

    def test_hoist_over_corner_block_carries_the_corner_node(self):
        corner = TrussSegment("K", "", "Corner", Point3D(6000, 0, 0),
                              self_weight_kg=10, width_mm=290, height_mm=290,
                              corner_type="L_Corner")
        _, result, _ = solve(
            [line("A", (0, 0, 0), (6000, 0, 0), 60), corner,
             line("B", (6250, 250, 0), (6250, 4250, 0), 40)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (6250, 0, 0)),
             hoist("H3", (6250, 4250, 0))])
        values = reactions(result)
        by_id = {item["support_id"]: item for item in result["reactions"]}
        self.assertAlmostEqual(by_id["H2"]["position_mm"][0], 6250.0, delta=1)
        self.assertAlmostEqual(by_id["H2"]["position_mm"][1], 0.0, delta=1)
        # Supports at (0,0), (6250,0), (6250,4250): moments about x = 6250.
        self.assertAlmostEqual(values["H1"], 60.0*3250.0/6250.0, delta=0.01)
        self.assertAlmostEqual(values["H3"], 40.0*2250.0/4250.0, delta=0.01)

    def test_full_circle_of_arc_segments(self):
        radius, width = 3856.5, 287.0
        center = (0.0, 0.0)
        segments = []
        for index in range(8):
            angle = radians(45.0*index)
            segments.append(TrussSegment(
                "C%d" % index, "", "Circle",
                Point3D(center[0]+radius*cos(angle),
                        center[1]+radius*sin(angle), 145.0),
                nominal_length_mm=radius*pi/4.0, z_rotation_deg=45.0*index,
                symbol="HOFKon 290-4 Circle R4000 / D8000", width_mm=width,
                height_mm=width, self_weight_kg=30.0,
                bbox=BoundingBox(Point3D(9e6, 9e6), Point3D(9e6+1, 9e6+1)),
                mechanical_section=section()))
        hoists = [hoist("H%d" % k, (radius*cos(radians(45+90*k)),
                                    radius*sin(radians(45+90*k)), 145.0))
                  for k in range(4)]
        construction, result, document = solve(segments, hoists)
        self.assertEqual(document.unassigned_supports, [])
        self.assertTrue(all(item.arc is not None for item in segments))
        self.assertTrue(result["writeback_eligible"], result["issues"])
        for value in reactions(result).values():
            self.assertAlmostEqual(value, 60.0, delta=0.05)

    def test_two_hoists_cannot_stabilise_an_l_frame(self):
        _, result, _ = solve(
            [line("A", (0, 0, 0), (6000, 0, 0), 60),
             line("B", (6000, 0, 0), (6000, 4000, 0), 40)],
            [hoist("H1", (0, 0, 0)), hoist("H2", (6000, 4000, 0))])
        self.assertFalse(result["writeback_eligible"])
        self.assertIn("lateral_or_roll_stability_not_provided_by_supports",
                      result["issues"])


class VerticalPickupTests(unittest.TestCase):
    def test_hung_load_and_hoist_attach_directly_below_in_plan(self):
        # 30 degree truss; the load hangs 440 mm below the axis.  The nearest
        # 3D point would slide ~220 mm down the slope (B3 regression).
        rise = 6000.0*3.0**-0.5
        truss = line("I", (0, 0, 0), (6000, 0, rise), 0)
        middle_z = rise/2.0
        construction, result, _ = solve(
            [truss], [hoist("H1", (500, 0, 500*rise/6000-300)),
                      hoist("H2", (5500, 0, 5500*rise/6000-300))],
            [load("P", (3000, 0, middle_z-440), 200)])
        attached = construction.point_loads[0].attachment
        self.assertAlmostEqual(attached.projected_x, 3000.0, delta=0.5)
        hoists = {item.item.id: item.attachment for item in
                  construction.supports}
        self.assertAlmostEqual(hoists["H1"].projected_x, 500.0, delta=0.5)
        for value in reactions(result).values():
            self.assertAlmostEqual(value, 100.0, delta=0.01)


class TransferredLoadTests(unittest.TestCase):
    frame = staticmethod(lambda: [
        line("S1", (0, 0, 0), (6000, 0, 0), 0),
        line("S2", (6000, 0, 0), (6000, 6000, 0), 0),
        line("S3", (6000, 6000, 0), (0, 6000, 0), 0),
        line("S4", (0, 6000, 0), (0, 0, 0), 0)])
    corners = [(0, 0, 0), (6000, 0, 0), (6000, 6000, 0), (0, 6000, 0)]

    def test_located_transfer_is_applied_on_its_member(self):
        transfer = {"source_id": "LOW:H9", "mass_kg": 100.0,
                    "source_type": "transferred_high_hook_load",
                    "station_mm": None, "truss_id": "S1", "local_mm": 3000.0}
        _, result, _ = solve(self.frame(),
                             [hoist("H%d" % i, p)
                              for i, p in enumerate(self.corners)],
                             [load("P", (3000, 6000, 0), 1)], [transfer])
        self.assertAlmostEqual(result["total_applied_mass_kg"], 101.0)
        values = reactions(result)
        # S1 is supported at both ends (H0, H1); the 1 kg load is on S3.
        self.assertAlmostEqual(values["H0"]+values["H1"], 100.0, delta=0.01)
        self.assertTrue(result["writeback_eligible"])

    def test_unlocated_transfer_is_never_dropped_silently(self):
        transfer = {"source_id": "LOW:H9", "mass_kg": 100.0,
                    "source_type": "transferred_high_hook_load",
                    "station_mm": 1000.0}
        _, result, _ = solve(self.frame(),
                             [hoist("H%d" % i, p)
                              for i, p in enumerate(self.corners)],
                             [load("P", (3000, 6000, 0), 1)], [transfer])
        self.assertIn("transferred_load_location_unsupported_in_general_frame",
                      result["issues"])
        self.assertFalse(result["writeback_eligible"])


if __name__ == "__main__":
    unittest.main()
