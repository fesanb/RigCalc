"""One construction must never abort the whole run (Vectorworks test file).

Regression for an inclined chain containing a corner block: corner items
have no start/end chord, and the inclined geometry reduction crashed with
``AttributeError`` before any result or report was written.
"""

import unittest
from unittest import mock

from rigcalc.model import (DocumentModel, Point3D, PointLoad, Support,
                           TrussSegment)
from rigcalc.notifications import evaluate_notifications
from rigcalc.report.calculation_report import make_calculation_text
from rigcalc.report.hoist_outcomes import build_hoist_outcomes
from rigcalc.solver import calculate_corotational_reactions, calculate_reactions
from rigcalc.solver import system
from rigcalc.solver.comparison import select_primary_calculation
from rigcalc.solver.inclined_beam import solve_inclined_planar_frame
from rigcalc.solver.inclined_corotational import (
    solve_inclined_corotational_beam)
from rigcalc.solver.inclined_geometry import inclined_station_coordinates
from rigcalc.topology import build_constructions
from tests.test_continuous_beam import construction


def inclined_chain_with_corner():
    item = construction(6000, [0, 6000], total_mass_kg=50)
    item.truss_segments[0].end = Point3D(6000, 0, 1000)
    corner = TrussSegment("K1", "Corner", "Corner", Point3D(6000, 0, 1000),
                          0.0, None, None)
    item.truss_segments.append(corner)
    item.ordered_truss_ids.append(corner.id)
    return item


def two_level_trusses():
    trusses, supports, loads = [], [], []
    for index, y in enumerate((0, 10000)):
        start, end = Point3D(0, y), Point3D(6000, y)
        trusses.append(TrussSegment(
            "T{}".format(index+1), "Truss", "Line", start, 6000, start, end,
            self_weight_kg=60))
        supports.extend([
            Support("H{}a".format(index+1), "", Point3D(0, y),
                    weight_with_chain_kg=10, capacity_kg=500,
                    support_kind="hoist"),
            Support("H{}b".format(index+1), "", Point3D(6000, y),
                    weight_with_chain_kg=10, capacity_kg=500,
                    support_kind="hoist")])
        loads.append(PointLoad("L{}".format(index+1), "",
                               Point3D(3000, y), "Load", 100))
    return DocumentModel(trusses=trusses, supports=supports, point_loads=loads)


class CornerInInclinedChainTests(unittest.TestCase):
    def test_geometry_reduction_reports_corner_instead_of_crashing(self):
        coordinates, issue = inclined_station_coordinates(
            inclined_chain_with_corner())
        self.assertIsNone(coordinates)
        self.assertEqual(
            issue, "unsupported_non_line_member_in_inclined_chain:K1:Corner")

    def test_both_inclined_solvers_fail_closed(self):
        for solver in (solve_inclined_planar_frame,
                       solve_inclined_corotational_beam):
            item = inclined_chain_with_corner()
            from rigcalc.solver.beam_statics import trace_construction_loads
            result = solver(item, trace_construction_loads(item))
            self.assertEqual(result["status"], "not_calculated")
            self.assertFalse(result["writeback_eligible"])
            self.assertIn(
                "unsupported_non_line_member_in_inclined_chain:K1:Corner",
                result["issues"])


class GuardedConstructionSolveTests(unittest.TestCase):
    def test_solver_exception_affects_only_its_own_construction(self):
        document = two_level_trusses()
        constructions = build_constructions(document)
        self.assertEqual(len(constructions), 2)
        failing_id = constructions[0].id
        original = system._solve_local

        def flaky(construction, loads):
            if construction.id == failing_id:
                raise AttributeError("'NoneType' object has no attribute 'x'")
            return original(construction, loads)

        with mock.patch.object(system, "_solve_local", flaky):
            linear = calculate_reactions(document, constructions)
        by_id = {item["construction_id"]: item
                 for item in linear["constructions"]}
        failed = by_id[failing_id]
        self.assertEqual(failed["status"], "not_calculated")
        self.assertFalse(failed["writeback_eligible"])
        self.assertTrue(failed["issues"][0].startswith(
            "internal_solver_error:AttributeError"))
        other = by_id[constructions[1].id]
        self.assertEqual(other["status"], "preliminary")
        self.assertTrue(other["writeback_eligible"])

        # The failed result must flow through the downstream reports and
        # give its hoists an explicit zero outcome with the error reason.
        nonlinear = calculate_corotational_reactions(document, constructions)
        primary = select_primary_calculation(linear, nonlinear)
        make_calculation_text(primary)
        evaluate_notifications(primary)
        outcomes = {item["support_id"]: item for item in build_hoist_outcomes(
            document, primary, topology_constructions=constructions)}
        failed_hoists = [item.item.id for item in constructions[0].supports]
        self.assertTrue(failed_hoists)
        for support_id in failed_hoists:
            self.assertEqual(outcomes[support_id]["status"],
                             "zero_not_calculated")
            self.assertEqual(outcomes[support_id]["high_hook_mass_kg"], 0.0)
            self.assertIn("internal_solver_error",
                          outcomes[support_id]["reason"])


if __name__ == "__main__":
    unittest.main()
