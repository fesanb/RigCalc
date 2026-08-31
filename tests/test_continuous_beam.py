import unittest

from rigcalc.model import (AttachedObject, Attachment, Construction,
                           DistributedLoad, MechanicalSection, Point3D,
                           PointLoad,
                           StationRange, Support, TrussSegment)
from rigcalc.solver.beam_statics import (solve_inclined_two_support_beam,
                                         trace_construction_loads)
from rigcalc.solver.continuous_beam import solve_continuous_beam
from rigcalc.report.calculation_report import make_calculation_text
from rigcalc.solver.inclined_geometry import inclined_station_coordinates
from rigcalc.solver.inclined_beam import solve_inclined_planar_frame
from tests.reference_beam_solver import solve_uniform_beam


def attachment(station):
    return Attachment("T1", "", 0, station, station, station, 0)


def section(identifier="S", inertia_m4=1.0e-5):
    return MechanicalSection(
        identifier, identifier, "", "", 0.01, 0.01, 0.01,
        1.0e-5, inertia_m4, inertia_m4,
        70.0e9, 26.0e9, 0.3, 2700, "")


def construction(length_mm, support_stations, total_mass_kg=100.0,
                 segment_sections=None, point_loads=None):
    boundaries = [0.0, length_mm]
    if segment_sections:
        boundaries = [item[0] for item in segment_sections] + [length_mm]
    else:
        segment_sections = [(0.0, section())]
    trusses, station_map = [], {}
    for index, ((start, mechanical), end) in enumerate(
            zip(segment_sections, boundaries[1:])):
        truss_id = "T{}".format(index + 1)
        trusses.append(TrussSegment(
            truss_id, "", "Line", Point3D(start, 0), end-start,
            Point3D(start, 0), Point3D(end, 0),
            mechanical_section=mechanical))
        station_map[truss_id] = StationRange(start, end, "forward")
    supports = [AttachedObject(
        Support("H{}".format(index + 1), "", Point3D(station, 0)),
        attachment(station)) for index, station in enumerate(support_stations)]
    distributed_loads = []
    if total_mass_kg:
        distributed = DistributedLoad(
            "DL", "", Point3D(0, 0), "Load", total_mass_kg=total_mass_kg,
            mass_per_m_kg=total_mass_kg/(length_mm/1000.0),
            length_mm=length_mm)
        distributed_loads.append(AttachedObject(distributed, attachment(0)))
    return Construction(
        "C", trusses, [], "open_chain",
        ordered_truss_ids=[item.id for item in trusses],
        station_map=station_map, supports=supports,
        point_loads=point_loads or [], distributed_loads=distributed_loads,
        nominal_truss_length_mm=length_mm, structural_span_mm=length_mm)


def solve(item):
    return solve_continuous_beam(item, trace_construction_loads(item))


class ContinuousBeamTests(unittest.TestCase):
    def test_two_equal_spans_under_uniform_load_matches_classic_reactions(self):
        section = MechanicalSection(
            "S", "S", "", "", 0.01, 0.01, 0.01,
            1.0e-5, 1.0e-5, 1.0e-5, 70.0e9, 26.0e9, 0.3, 2700, "")
        truss = TrussSegment(
            "T1", "", "Line", Point3D(0, 0), 10000,
            Point3D(0, 0), Point3D(10000, 0), mechanical_section=section)
        supports = [
            AttachedObject(Support("H1", "", Point3D(0, 0)), attachment(0)),
            AttachedObject(Support("H2", "", Point3D(5000, 0)), attachment(5000)),
            AttachedObject(Support("H3", "", Point3D(10000, 0)), attachment(10000)),
        ]
        distributed = DistributedLoad(
            "L1", "", Point3D(0, 0), "Load",
            total_mass_kg=100, mass_per_m_kg=10, length_mm=10000)
        construction = Construction(
            "C", [truss], [], "open_chain", ordered_truss_ids=["T1"],
            station_map={"T1": StationRange(0, 10000, "forward")},
            supports=supports,
            distributed_loads=[AttachedObject(distributed, attachment(0))],
            nominal_truss_length_mm=10000, structural_span_mm=10000)
        result = solve_continuous_beam(
            construction, trace_construction_loads(construction))
        self.assertEqual(result["status"], "preliminary")
        self.assertFalse(result["writeback_eligible"])
        self.assertFalse(result["validation"]["support_model_valid"])
        self.assertIn("tension_only_contact_mass_model_not_implemented",
                      result["issues"])
        self.assertEqual(
            result["active_set_validation"]["method"],
            "exhaustive_tension_only_active_set")
        self.assertTrue(result["validation"]["vertical_equilibrium_ok"])
        self.assertTrue(result["validation"]["moment_equilibrium_ok"])
        reactions = [item["reaction_mass_kg"] for item in result["reactions"]]
        self.assertAlmostEqual(reactions[0], 18.75, places=5)
        self.assertAlmostEqual(reactions[1], 62.5, places=5)
        self.assertAlmostEqual(reactions[2], 18.75, places=5)
        self.assertAlmostEqual(sum(reactions), 100.0, places=6)
        self.assertEqual([item["station_mm"] for item in result["stations"]],
                         [0, 2500, 5000, 7500, 10000])
        self.assertEqual(len(result["element_forces"]), 4)
        first = result["element_forces"][0]
        self.assertEqual(first["start_station_mm"], 0)
        self.assertEqual(first["end_station_mm"], 2500)
        self.assertIn("Vz_n", first["i"])
        self.assertIn("My_nm", first["j"])
        self.assertIn("uz_m", result["stations"][1]["displacements"])
        self.assertEqual(len(result["deflection"]["spans"]), 2)
        self.assertEqual(
            result["deflection"]["spans"][0]["midspan"]["station_mm"],
            2500)
        self.assertLess(
            result["deflection"]["spans"][0]["midspan"]["deflection_mm"],
            0.0)

    def test_simply_supported_uniform_load_for_different_spans(self):
        for length_mm in (3000, 7000, 13000):
            with self.subTest(length_mm=length_mm):
                result = solve(construction(
                    length_mm, [0, length_mm], total_mass_kg=240))
                reactions = [item["reaction_mass_kg"]
                             for item in result["reactions"]]
                self.assertAlmostEqual(reactions[0], 120.0, places=6)
                self.assertAlmostEqual(reactions[1], 120.0, places=6)

    def test_mixed_uniform_and_point_load_matches_two_support_statics(self):
        point = PointLoad("P", "", Point3D(2500, 0), "Load", 60.0)
        result = solve(construction(
            10000, [0, 10000], total_mass_kg=100,
            point_loads=[AttachedObject(point, attachment(2500))]))
        reactions = [item["reaction_mass_kg"] for item in result["reactions"]]
        # Uniform 100 kg gives 50/50; 60 kg at one quarter gives 45/15.
        self.assertAlmostEqual(reactions[0], 95.0, places=6)
        self.assertAlmostEqual(reactions[1], 65.0, places=6)
        self.assertTrue(result["validation"]["vertical_equilibrium_ok"])
        self.assertTrue(result["validation"]["moment_equilibrium_ok"])

    def test_engaged_level_contact_state_includes_hoist_chain_mass(self):
        item = construction(10000, [0, 10000], total_mass_kg=100)
        item.supports[0].item.weight_with_chain_kg = 10.0
        item.supports[1].item.weight_with_chain_kg = 20.0
        result = solve(item)
        self.assertAlmostEqual(result["total_applied_mass_kg"], 130.0,
                               places=6)
        self.assertAlmostEqual(sum(item["reaction_mass_kg"]
                                   for item in result["reactions"]), 130.0,
                               places=6)
        self.assertTrue(result["validation"]["support_model_valid"])
        self.assertFalse(result["writeback_eligible"])
        self.assertEqual(result["reactions"][0]["contact_mass_included_kg"],
                         10.0)
        self.assertIn(
            "tension_only_contact_model_diagnostic_not_writeback_source",
            result["issues"])

    def test_extreme_support_spacing_remains_numerically_auditable(self):
        result = solve(construction(
            20000, [0, 25, 20000], total_mass_kg=200,
            segment_sections=[(0, section("A", 1.0e-7)),
                              (25, section("B", 1.0e-3))]))
        self.assertEqual(result["status"], "preliminary")
        self.assertTrue(result["validation"]["numerically_valid"])
        self.assertLess(
            result["numerical_diagnostics"]["relative_reduced_residual"],
            1.0e-8)
        self.assertGreater(
            result["numerical_diagnostics"]["minimum_scaled_pivot"], 0.0)

    def test_overhang_point_load_matches_static_reference_and_keeps_uplift(self):
        load = PointLoad("P", "", Point3D(10000, 0), "Load", 120.0)
        item = construction(
            10000, [2000, 8000], total_mass_kg=0,
            point_loads=[AttachedObject(load, attachment(10000))])
        result = solve(item)
        reactions = [value["reaction_mass_kg"] for value in result["reactions"]]
        self.assertAlmostEqual(reactions[0], -40.0, places=6)
        self.assertAlmostEqual(reactions[1], 160.0, places=6)
        self.assertAlmostEqual(sum(reactions), 120.0, places=6)

    def test_piecewise_ei_changes_reactions_but_preserves_equilibrium(self):
        uniform = construction(
            10000, [0, 4000, 10000], total_mass_kg=100,
            segment_sections=[(0, section("A")), (4000, section("B"))])
        variable = construction(
            10000, [0, 4000, 10000], total_mass_kg=100,
            segment_sections=[(0, section("A", 1.0e-5)),
                              (4000, section("B", 4.0e-5))])
        uniform_reactions = [item["reaction_mass_kg"]
                             for item in solve(uniform)["reactions"]]
        variable_reactions = [item["reaction_mass_kg"]
                              for item in solve(variable)["reactions"]]
        # Clapeyron's three-moment equation for L1=4 m, L2=6 m,
        # q=10 kg/m, EI2=4*EI1 gives M_B=-295/11 kg*m.
        support_moment_kg_m = -295.0/11.0
        expected = [
            20.0 + support_moment_kg_m/4.0,
            100.0-(20.0 + support_moment_kg_m/4.0)-
            (30.0 + support_moment_kg_m/6.0),
            30.0 + support_moment_kg_m/6.0,
        ]
        self.assertAlmostEqual(sum(variable_reactions), 100.0, places=6)
        for actual, reference in zip(variable_reactions, expected):
            self.assertAlmostEqual(actual, reference, places=5)
        self.assertGreater(max(abs(a-b) for a, b in
                               zip(uniform_reactions, variable_reactions)), 1.0)

    def test_truss_self_weight_is_uniform_and_independent_of_segmentation(self):
        one_piece = construction(
            10000, [0, 5000, 10000], total_mass_kg=0,
            segment_sections=[(0, section())])
        one_piece.truss_segments[0].self_weight_kg = 100.0
        four_pieces = construction(
            10000, [0, 5000, 10000], total_mass_kg=0,
            segment_sections=[
                (0, section()), (2500, section()),
                (5000, section()), (7500, section()),
            ])
        for truss in four_pieces.truss_segments:
            truss.self_weight_kg = 25.0

        one_load = trace_construction_loads(one_piece)[0]
        self.assertEqual(one_load["interval_start_mm"], 0)
        self.assertEqual(one_load["interval_end_mm"], 10000)
        self.assertAlmostEqual(one_load["mass_per_m_kg"], 10.0)

        one_reactions = [item["reaction_mass_kg"] for item in solve(one_piece)["reactions"]]
        four_reactions = [item["reaction_mass_kg"] for item in solve(four_pieces)["reactions"]]
        for actual, expected in zip(one_reactions, (18.75, 62.5, 18.75)):
            self.assertAlmostEqual(actual, expected, places=5)
        for actual, expected in zip(four_reactions, one_reactions):
            self.assertAlmostEqual(actual, expected, places=5)

    def test_truss_self_weight_uses_physical_interval_when_stationing_is_reversed(self):
        item = construction(
            10000, [0, 5000, 10000], total_mass_kg=0,
            segment_sections=[(0, section())])
        item.truss_segments[0].self_weight_kg = 100.0
        item.station_map["T1"] = StationRange(10000, 0, "reverse")

        load = trace_construction_loads(item)[0]
        self.assertEqual(load["interval_start_mm"], 0)
        self.assertEqual(load["interval_end_mm"], 10000)
        self.assertEqual(load["station_mm"], 5000)
        self.assertAlmostEqual(load["mass_per_m_kg"], 10.0)

    def test_inclined_truss_is_rejected_by_planar_beam_solver(self):
        item = construction(10000, [0, 5000, 10000], total_mass_kg=100)
        item.truss_segments[0].end = Point3D(10000, 0, 1000)
        result = solve(item)
        self.assertEqual(result["status"], "not_calculated")
        self.assertIn("unsupported_inclined_truss_geometry:T1", result["issues"])

    def test_inclined_station_geometry_reduces_a_collinear_chain_to_vertical_plane(self):
        item = construction(
            6000, [0, 6000], total_mass_kg=0,
            segment_sections=[(0, section()), (3000, section())])
        item.truss_segments[0].start = Point3D(0, 0, 1000)
        item.truss_segments[0].end = Point3D(3000, 0, 4000)
        item.truss_segments[1].start = Point3D(3000, 0, 4000)
        item.truss_segments[1].end = Point3D(6000, 0, 7000)
        coordinates, issue = inclined_station_coordinates(item)
        self.assertIsNone(issue)
        self.assertEqual(coordinates[0], (0, 1000))
        self.assertEqual(coordinates[3000], (3000, 4000))
        self.assertEqual(coordinates[6000], (6000, 7000))

    def test_inclined_two_support_result_is_diagnostic_only(self):
        item = construction(6000, [0, 6000], total_mass_kg=100)
        item.truss_segments[0].end = Point3D(6000, 0, 3000)
        result = solve_inclined_two_support_beam(
            item, trace_construction_loads(item))
        self.assertEqual(result["status"], "diagnostic")
        self.assertFalse(result["writeback_eligible"])
        self.assertAlmostEqual(result["reactions"][0]["reaction_mass_kg"], 50)
        self.assertAlmostEqual(result["reactions"][1]["reaction_mass_kg"], 50)

    def test_inclined_frame_preserves_total_global_distributed_gravity(self):
        item = construction(6000, [0, 6000], total_mass_kg=100)
        item.truss_segments[0].end = Point3D(6000, 0, 3000)
        result = solve_inclined_planar_frame(item, trace_construction_loads(item))
        self.assertEqual(result["status"], "diagnostic")
        self.assertAlmostEqual(sum(value["reaction_mass_kg"]
                                   for value in result["reactions"]), 100.0)
        self.assertLess(
            result["numerical_diagnostics"]["relative_reduced_residual"],
            1.0e-8)

    def test_inclined_frame_asymmetric_point_load_matches_global_statics(self):
        load = PointLoad("P", "", Point3D(600, 0, 800), "Load", 100)
        item = construction(
            5000, [0, 5000], total_mass_kg=0,
            point_loads=[AttachedObject(load, attachment(1000))])
        item.truss_segments[0].end = Point3D(3000, 0, 4000)
        result = solve_inclined_planar_frame(item, trace_construction_loads(item))
        reactions = [item["reaction_mass_kg"] for item in result["reactions"]]
        self.assertAlmostEqual(reactions[0], 80.0, places=5)
        self.assertAlmostEqual(reactions[1], 20.0, places=5)
        self.assertTrue(result["validation"]["vertical_equilibrium_ok"])
        self.assertTrue(result["validation"]["moment_equilibrium_ok"])

    def test_inclined_frame_contact_state_includes_engaged_hoist_chain_mass(self):
        item = construction(6000, [0, 6000], total_mass_kg=100)
        item.truss_segments[0].end = Point3D(6000, 0, 3000)
        item.supports[0].item.weight_with_chain_kg = 10.0
        item.supports[1].item.weight_with_chain_kg = 20.0
        result = solve_inclined_planar_frame(
            item, trace_construction_loads(item))
        self.assertEqual(result["status"], "diagnostic")
        self.assertFalse(result["writeback_eligible"])
        self.assertAlmostEqual(result["total_applied_mass_kg"], 130.0,
                               places=4)
        self.assertAlmostEqual(sum(value["reaction_mass_kg"]
                                   for value in result["reactions"]), 130.0,
                               places=4)
        self.assertEqual(result["reactions"][0]["contact_mass_included_kg"],
                         10.0)
        self.assertEqual(result["reactions"][1]["contact_mass_included_kg"],
                         20.0)
        self.assertIn(
            "tension_only_contact_model_diagnostic_not_writeback_source",
            result["issues"])

    def test_uniform_load_equilibrium_and_support_deflection_for_2_to_20_supports(self):
        length_mm = 19000.0
        for support_count in range(2, 21):
            with self.subTest(support_count=support_count):
                spacing = length_mm/(support_count-1)
                support_stations = [index*spacing
                                    for index in range(support_count)]
                result = solve(construction(
                    length_mm, support_stations, total_mass_kg=380))
                self.assertEqual(result["status"], "preliminary")
                self.assertEqual(len(result["reactions"]), support_count)
                self.assertAlmostEqual(sum(
                    item["reaction_mass_kg"]
                    for item in result["reactions"]), 380.0, places=5)
                station_lookup = {
                    round(item["station_mm"], 6): item
                    for item in result["stations"]}
                for station in support_stations:
                    self.assertAlmostEqual(
                        station_lookup[round(station, 6)]
                        ["displacements"]["uz_m"], 0.0, places=12)

    def test_matches_independent_two_dof_reference_solver(self):
        elastic_modulus = 70.0e9
        for support_count in (3, 4, 7, 12, 20):
            with self.subTest(support_count=support_count):
                stations_m = [float(index) for index in range(support_count)]
                support_stations = [value*1000.0 for value in stations_m]
                result = solve(construction(
                    support_stations[-1], support_stations,
                    total_mass_kg=10.0*(support_count-1)))
                expected_n = solve_uniform_beam(
                    stations_m, list(range(support_count)),
                    [elastic_modulus*1.0e-5]*(support_count-1),
                    10.0*9.80665)
                actual_n = [item["reaction_mass_kg"]*9.80665
                            for item in result["reactions"]]
                for actual, expected in zip(actual_n, expected_n):
                    self.assertAlmostEqual(actual, expected, places=5)

    def test_negative_hoists_are_released_and_system_is_resolved(self):
        load = PointLoad("P", "", Point3D(19000, 0), "Load", 2000.0)
        item = construction(
            57000, [1792, 33000, 43508, 49228, 55228], total_mass_kg=0,
            point_loads=[AttachedObject(load, attachment(19000))])
        result = solve(item)
        active = [reaction for reaction in result["reactions"]
                  if reaction["support_active"]]
        released = [reaction for reaction in result["reactions"]
                    if not reaction["support_active"]]
        self.assertTrue(released)
        self.assertTrue(all(reaction["reaction_mass_kg"] >= -1.0e-6
                            for reaction in active))
        self.assertAlmostEqual(sum(
            reaction["reaction_mass_kg"]
            for reaction in result["reactions"]), 2000.0, places=4)
        self.assertFalse(result["writeback_eligible"])
        self.assertTrue(result["validation"]["moment_equilibrium_ok"])
        self.assertAlmostEqual(
            result["validation"]["moment_equilibrium_error_kg_m"],
            0.0, places=8)
        self.assertEqual(
            result["validation"]["reaction_equilibrium_correction"]["method"],
            "two_active_support_static_equilibrium")
        report = make_calculation_text({"constructions": [result]})
        self.assertIn("Validation: equilibrium=yes support model=no", report)
        self.assertIn("Numerical diagnostics: method=scaled_partial_pivoting",
                      report)
        self.assertIn("unconstrained signed reaction", report)

    def test_unproven_tension_only_set_is_diagnostic_and_writeback_blocked(self):
        load = PointLoad("P", "", Point3D(10000, 0), "Load", 120.0)
        item = construction(
            10000, [2000, 8000], total_mass_kg=0,
            point_loads=[AttachedObject(load, attachment(10000))])
        result = solve(item)
        self.assertEqual(result["status"], "diagnostic")
        self.assertFalse(result["writeback_eligible"])
        self.assertIn("tension_only_active_set_no_feasible_solution",
                      result["issues"])

    def test_tension_only_search_limit_is_diagnostic_and_writeback_blocked(self):
        stations = [index*1000.0 for index in range(1, 10)]
        load = PointLoad("P", "", Point3D(0, 0), "Load", 1000.0)
        result = solve(construction(
            10000, stations, total_mass_kg=0,
            point_loads=[AttachedObject(load, attachment(0))]))
        self.assertEqual(result["status"], "diagnostic")
        self.assertFalse(result["writeback_eligible"])
        self.assertIn("tension_only_active_set_limit_exceeded",
                      result["issues"])


if __name__ == "__main__":
    unittest.main()
