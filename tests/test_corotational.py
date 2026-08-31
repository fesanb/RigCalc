import unittest

from rigcalc.solver.corotational import (
    CorotationalElement, CorotationalModel, CorotationalNode,
    solve_corotational)
from rigcalc.solver.beam_statics import trace_construction_loads
from rigcalc.solver.nonlinear_beam import solve_corotational_beam
from rigcalc.solver.nonlinear_beam import calculate_corotational_reactions
from rigcalc.model import DocumentModel
from tests.test_continuous_beam import construction, section


class CorotationalTests(unittest.TestCase):
    def test_simply_supported_beam_converges_and_roller_moves_horizontally(self):
        model = CorotationalModel(
            nodes=[
                CorotationalNode("A", 0, 0, restrained=(True, True, False)),
                CorotationalNode("B", 5, 0, load=(0, -1000, 0)),
                CorotationalNode("C", 10, 0, restrained=(False, True, False)),
            ],
            elements=[
                CorotationalElement("E1", "A", "B", 70e9, 0.01, 1e-4),
                CorotationalElement("E2", "B", "C", 70e9, 0.01, 1e-4),
            ])
        result = solve_corotational(model)
        self.assertTrue(result["converged"])
        self.assertAlmostEqual(result["node_reactions"]["A"][1], 500, places=3)
        self.assertAlmostEqual(result["node_reactions"]["C"][1], 500, places=3)
        self.assertLess(result["node_displacements"]["C"][0], 0.0)
        linear_deflection = -1000*10**3/(48*70e9*1e-4)
        self.assertAlmostEqual(
            result["node_displacements"]["B"][1], linear_deflection,
            delta=abs(linear_deflection)*0.01)

    def test_construction_adapter_reports_horizontal_support_motion(self):
        item = construction(
            10000, [0, 10000], total_mass_kg=100,
            segment_sections=[(0, section()), (5000, section())])
        result = solve_corotational_beam(
            item, trace_construction_loads(item))
        self.assertEqual(result["status"], "diagnostic")
        self.assertTrue(result["converged"])
        self.assertTrue(result["validation"]["vertical_equilibrium_ok"])
        self.assertTrue(result["validation"]["moment_equilibrium_ok"])
        self.assertEqual(len(result["stations"]), 3)
        self.assertLess(result["stations"][-1]["displacements"]["ux_m"], 0.0)
        self.assertFalse(result["writeback_eligible"])

    def test_diagnostic_nonlinear_reaction_is_not_transferred(self):
        lower = construction(10000, [0, 10000], total_mass_kg=100)
        lower.id = "LOWER"
        lower.supports[0].item.transfer_target_construction_id = "UPPER"
        lower.supports[0].item.transfer_target_station_mm = 5000
        upper = construction(
            10000, [0, 10000], total_mass_kg=0,
            segment_sections=[(0, section()), (5000, section())])
        upper.id = "UPPER"
        result = calculate_corotational_reactions(
            DocumentModel(), [upper, lower])
        by_id = {item["construction_id"]: item
                 for item in result["constructions"]}
        transferred = [item for item in by_id["UPPER"]["loads"]
                       if item["source_type"] ==
                       "transferred_nonlinear_high_hook_load"]
        self.assertEqual(transferred, [])
        self.assertIn(
            "upstream_nonlinear_load_transfer_ineligible:LOWER",
            by_id["UPPER"]["issues"])


if __name__ == "__main__":
    unittest.main()
