"""Tension-only hoist contact: release rule, cable slack and re-engagement.

Reference case (T10#3-style, GitHub issue #7): a 10 m truss on hoists at
0, 2 and 8 m, 50 kg uniform self-weight, 60 kg at the 10 m overhang and
15 kg hoist/chain mass per hoist.  Hoist/chain mass is never a truss load;
it always ends in the top hook.  Unconstrained, H2 needs a downward reaction
(uplift).  Physically the truss rises at H2 so its chain goes slack; H1 and
H3 carry the load.  Hand statics about H1 with H2 released:

    H3 = (50*5 + 60*10)/8 = 106.25 kg
    H1 = 110 - 106.25     =   3.75 kg
    High Hook = reaction + 15 kg; slack H2 High Hook = 15 kg
"""

import unittest

from rigcalc.model import AttachedObject, Point3D, PointLoad
from rigcalc.report.calculation_report import make_calculation_text
from rigcalc.solver.beam_statics import trace_construction_loads
from rigcalc.solver.contact import released_contact_is_slack
from rigcalc.solver.continuous_beam import solve_continuous_beam
from rigcalc.solver.corotational import (CorotationalElement,
                                         CorotationalModel, CorotationalNode,
                                         solve_corotational)
from rigcalc.solver.inclined_beam import solve_inclined_planar_frame
from rigcalc.solver.inclined_corotational import (
    solve_inclined_corotational_beam)
from rigcalc.solver.nonlinear_beam import solve_corotational_beam
from tests.test_continuous_beam import attachment, construction

INCLINE_RISE_MM = 5000.0
EXPECTED_H1_KG = 3.75
EXPECTED_H3_KG = 106.25
OVERHANG_LOAD_KG = 60.0
CHAIN_KG = 15.0


def overhang_case(rise_mm=0.0, motor_points=False, contact_mass_kg=CHAIN_KG):
    load = PointLoad("P", "", Point3D(10000, 0), "Load", OVERHANG_LOAD_KG)
    item = construction(
        10000, [0, 2000, 8000], total_mass_kg=50,
        point_loads=[AttachedObject(load, attachment(10000))])
    if rise_mm:
        item.truss_segments[0].end = Point3D(10000, 0, rise_mm)
    for support in item.supports:
        support.item.weight_with_chain_kg = contact_mass_kg
        if motor_points:
            station = support.attachment.global_station_mm
            # Motor point 4 m above the pickup on the inclined chord.
            support.item.object_position = Point3D(
                station, 0, station*rise_mm/10000.0+4000.0)
    return item


def by_id(result):
    return {item["support_id"]: item for item in result["reactions"]}


class ReleasedContactRuleTests(unittest.TestCase):
    def test_rising_pickup_is_slack_and_sinking_pickup_is_not(self):
        self.assertTrue(released_contact_is_slack(0.004))
        self.assertTrue(released_contact_is_slack(0.0))
        self.assertFalse(released_contact_is_slack(-0.004))
        self.assertFalse(released_contact_is_slack(None))

    def test_overhang_beyond_last_hoist_has_no_feasible_state(self):
        # Without chain mass on the truss, 120 kg at the overhang puts the
        # centre of gravity beyond H3: the truss would tip.  Fail closed.
        load = PointLoad("P", "", Point3D(10000, 0), "Load", 120.0)
        item = construction(
            10000, [0, 2000, 8000], total_mass_kg=50,
            point_loads=[AttachedObject(load, attachment(10000))])
        result = solve_continuous_beam(item, trace_construction_loads(item))
        self.assertIn("tension_only_active_set_no_feasible_solution",
                      result["issues"])
        self.assertFalse(result["writeback_eligible"])

    def test_level_chain_releases_the_uplift_hoist_not_a_sinking_one(self):
        result = solve_continuous_beam(
            overhang_case(), trace_construction_loads(overhang_case()))
        reactions = by_id(result)
        self.assertEqual(result["status"], "preliminary")
        self.assertFalse(reactions["H2"]["support_active"])
        self.assertTrue(reactions["H1"]["support_active"])
        self.assertAlmostEqual(reactions["H1"]["reaction_mass_kg"],
                               EXPECTED_H1_KG, places=6)
        self.assertAlmostEqual(reactions["H3"]["reaction_mass_kg"],
                               EXPECTED_H3_KG, places=6)
        self.assertLess(reactions["H2"]["unconstrained_reaction_mass_kg"], 0.0)
        displacement = {item["station_mm"]: item["displacements"]["uz_m"]
                        for item in result["stations"]}
        self.assertGreater(displacement[2000], 0.0)

    def test_inclined_linear_frame_uses_the_same_release_rule(self):
        item = overhang_case(INCLINE_RISE_MM)
        result = solve_inclined_planar_frame(
            item, trace_construction_loads(item))
        reactions = by_id(result)
        self.assertNotIn("tension_only_active_set_no_feasible_solution",
                         result["issues"])
        self.assertFalse(reactions["H2"]["support_active"])
        self.assertAlmostEqual(reactions["H1"]["reaction_mass_kg"],
                               EXPECTED_H1_KG, places=4)
        self.assertAlmostEqual(reactions["H3"]["reaction_mass_kg"],
                               EXPECTED_H3_KG, places=4)


class InclinedCorotationalLoadTests(unittest.TestCase):
    def test_inclined_distributed_load_matches_level_reference(self):
        # Three supports make the result statically indeterminate, so the
        # fixed-end moments of the distributed load directly affect it.
        level = construction(10000, [0, 2000, 8000], total_mass_kg=50)
        reference = [item["unconstrained_reaction_mass_kg"]
                     for item in solve_continuous_beam(
                         level, trace_construction_loads(level))["reactions"]]
        # Classic three-support values for this load (signed, kg).
        for actual, expected in zip(reference, (-1.875, 27.5, 24.375)):
            self.assertAlmostEqual(actual, expected, places=6)
        item = construction(10000, [0, 2000, 8000], total_mass_kg=50)
        item.truss_segments[0].end = Point3D(10000, 0, 1)
        ids = {"H1", "H2", "H3"}
        result = solve_inclined_corotational_beam(
            item, trace_construction_loads(item), _active_ids=ids)
        self.assertTrue(result["converged"])
        for actual, expected in zip(
                [entry["reaction_mass_kg"] for entry in result["reactions"]],
                reference):
            self.assertAlmostEqual(actual, expected, places=3)
        self.assertTrue(result["validation"]["moment_equilibrium_ok"])

    def test_light_load_on_stiff_frame_converges(self):
        model = CorotationalModel(
            nodes=[
                CorotationalNode("A", 0.0, 0.0, restrained=(True, True, False)),
                CorotationalNode("M", 5.0, 0.0, load=(0.0, -1.0, 0.0)),
                CorotationalNode("B", 10.0, 0.0,
                                 restrained=(False, True, False)),
            ],
            elements=[
                CorotationalElement("E1", "A", "M", 7.0e10, 1.0e-3, 1.0e-5),
                CorotationalElement("E2", "M", "B", 7.0e10, 1.0e-3, 1.0e-5),
            ])
        result = solve_corotational(model)
        self.assertTrue(result["converged"])
        self.assertAlmostEqual(result["node_reactions"]["A"][1], 0.5,
                               places=6)


class InclinedCableContactTests(unittest.TestCase):
    def solve(self):
        item = overhang_case(INCLINE_RISE_MM, motor_points=True)
        return solve_corotational_beam(item, trace_construction_loads(item))

    def test_uplift_hoist_goes_slack_and_load_redistributes(self):
        result = self.solve()
        reactions = by_id(result)
        self.assertEqual(result["status"], "diagnostic")
        self.assertEqual(result["method"],
                         "inclined_planar_corotational_tension_only_cable")
        self.assertEqual(reactions["H2"]["cable_state"], "slack")
        self.assertGreater(reactions["H2"]["cable_slack_mm"], 0.0)
        self.assertEqual(reactions["H2"]["reaction_mass_kg"], 0.0)
        self.assertEqual(reactions["H1"]["cable_state"], "taut")
        self.assertEqual(reactions["H3"]["cable_state"], "taut")
        # Geometric nonlinearity allows a small difference from first order.
        self.assertAlmostEqual(reactions["H1"]["reaction_mass_kg"],
                               EXPECTED_H1_KG, delta=0.5)
        self.assertAlmostEqual(reactions["H3"]["reaction_mass_kg"],
                               EXPECTED_H3_KG, delta=0.5)

    def test_chain_weight_goes_to_top_hook_not_the_truss(self):
        result = self.solve()
        reactions = by_id(result)
        self.assertAlmostEqual(result["total_applied_mass_kg"], 110.0)
        self.assertFalse(any(item["source_type"] == "hoist_chain_contact_mass"
                             for item in result["loads"]))
        self.assertAlmostEqual(reactions["H1"]["preliminary_high_hook_mass_kg"],
                               reactions["H1"]["reaction_mass_kg"]+CHAIN_KG)
        self.assertAlmostEqual(reactions["H2"]["preliminary_high_hook_mass_kg"],
                               CHAIN_KG)
        validation = result["contact_state_validation"]
        self.assertEqual(validation["method"],
                         "tension_only_cable_slack_reengagement")
        self.assertEqual(validation["released_support_ids"], ["H2"])

    def test_unconstrained_signed_result_is_retained(self):
        reactions = by_id(self.solve())
        self.assertLess(reactions["H2"]["unconstrained_reaction_mass_kg"],
                        -20.0)
        self.assertGreater(reactions["H1"]["unconstrained_reaction_mass_kg"],
                           0.0)

    def test_deformed_equilibrium_closes_and_result_stays_diagnostic(self):
        result = self.solve()
        validation = result["validation"]
        self.assertEqual(validation["equilibrium_configuration"], "deformed")
        self.assertTrue(validation["vertical_equilibrium_ok"])
        self.assertTrue(validation["moment_equilibrium_ok"])
        self.assertLess(abs(validation["horizontal_restraint_reaction_n"]), 1.0)
        self.assertFalse(result["writeback_eligible"])
        self.assertIn("diagnostic_not_writeback_source", result["issues"])

    def test_report_shows_slack_chain_and_contact_state(self):
        text = make_calculation_text({"constructions": [self.solve()]})
        self.assertIn("Contact state: method=tension_only_cable_slack_"
                      "reengagement slack chains=H2", text)
        self.assertIn("[chain slack", text)
        self.assertIn("[unconstrained signed reaction: -22.", text)

    def test_cable_and_fixed_contact_enumeration_agree(self):
        cable = by_id(self.solve())
        item = overhang_case(INCLINE_RISE_MM)
        fixed = by_id(solve_corotational_beam(
            item, trace_construction_loads(item)))
        for support_id in ("H1", "H2", "H3"):
            self.assertAlmostEqual(cable[support_id]["reaction_mass_kg"],
                                   fixed[support_id]["reaction_mass_kg"],
                                   delta=0.05)
            self.assertEqual(cable[support_id]["support_active"],
                             fixed[support_id]["support_active"])


if __name__ == "__main__":
    unittest.main()
