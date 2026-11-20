"""Benchmark suite for issues #4 and #5.

Every case runs through both the level continuous-beam solver and the
general 3D frame and is checked against closed-form results or the
independent two-DOF reference solver (``reference_beam_solver``).  Section:
E = 70 GPa, I = 1e-5 m^4 (EI = 7e5 N m^2).
"""

import unittest

from rigcalc.model import AttachedObject, Point3D, PointLoad
from rigcalc.solver.beam_statics import trace_construction_loads
from rigcalc.solver.continuous_beam import solve_continuous_beam
from rigcalc.solver.general_frame import solve_general_frame
from tests.reference_beam_solver import solve_beam
from tests.test_continuous_beam import attachment, construction

G = 9.80665
EI = 70.0e9*1.0e-5


def beam(length_mm, supports, mass=0.0, points=()):
    loads = [AttachedObject(PointLoad("P%d" % index, "", Point3D(station, 0),
                                      "Load", value), attachment(station))
             for index, (station, value) in enumerate(points)]
    return construction(length_mm, supports, total_mass_kg=mass,
                        point_loads=loads)


def solvers(item):
    loads = trace_construction_loads(item)
    return (("continuous_beam", solve_continuous_beam(item, loads)),
            ("general_frame", solve_general_frame(item, loads)))


def by_id(result, key="reaction_mass_kg"):
    return {item["support_id"]: item[key] for item in result["reactions"]}


class ClosedFormTests(unittest.TestCase):
    def test_two_equal_spans_point_load_gives_signed_uplift(self):
        # P at midspan of span 1 of two 5 m spans: 13P/32, 22P/32, -3P/32.
        for name, result in solvers(beam(10000, [0, 5000, 10000],
                                         points=[(2500, 320.0)])):
            with self.subTest(solver=name):
                signed = by_id(result, "unconstrained_reaction_mass_kg")
                self.assertAlmostEqual(signed["H1"], 130.0, delta=0.05)
                self.assertAlmostEqual(signed["H2"], 220.0, delta=0.05)
                self.assertAlmostEqual(signed["H3"], -30.0, delta=0.05)
                # Tension-only: H3 rises (slack); H1/H2 share P.
                active = by_id(result)
                self.assertAlmostEqual(active["H1"], 160.0, delta=0.05)
                self.assertAlmostEqual(active["H2"], 160.0, delta=0.05)
                self.assertAlmostEqual(active["H3"], 0.0, delta=0.05)
                self.assertTrue(result["writeback_eligible"])

    def test_three_equal_spans_uniform_load(self):
        # 0.4 / 1.1 / 1.1 / 0.4 wL for three spans of L = 4 m, w = 10 kg/m.
        for name, result in solvers(beam(12000, [0, 4000, 8000, 12000],
                                         mass=120.0)):
            with self.subTest(solver=name):
                values = by_id(result)
                for support, factor in zip(("H1", "H2", "H3", "H4"),
                                           (0.4, 1.1, 1.1, 0.4)):
                    self.assertAlmostEqual(values[support], factor*40.0,
                                           delta=0.01)

    def test_overhang_uniform_load(self):
        # Supports at 0 and 8 m, beam to 10 m, w = 10 kg/m.
        r2 = 10.0*10.0**2/(2*8.0)
        for name, result in solvers(beam(10000, [0, 8000], mass=100.0)):
            with self.subTest(solver=name):
                values = by_id(result)
                self.assertAlmostEqual(values["H2"], r2, delta=0.01)
                self.assertAlmostEqual(values["H1"], 100.0-r2, delta=0.01)

    def test_support_directly_below_point_load(self):
        for name, result in solvers(beam(10000, [0, 5000, 10000],
                                         points=[(5000, 200.0)])):
            with self.subTest(solver=name):
                values = by_id(result)
                self.assertAlmostEqual(values["H2"], 200.0, delta=0.01)
                self.assertAlmostEqual(values["H1"], 0.0, delta=0.01)

    def test_simply_supported_moment_and_deflection(self):
        # w = 9.80665 N/m over 10 m: M = wL^2/8, delta = 5wL^4/(384 EI).
        w = 10.0*G
        moment = w*10.0**2/8.0
        deflection_mm = 5.0*w*10.0**4/(384.0*EI)*1000.0
        for name, result in solvers(beam(10000, [0, 10000], mass=100.0)):
            if name == "continuous_beam":
                # Two supports use closed-form statics without a frame.
                continue
            with self.subTest(solver=name):
                peak = max(max(abs(element["i"]["My_nm"]),
                               abs(element["j"]["My_nm"]))
                           for element in result["element_forces"])
                self.assertAlmostEqual(peak, moment, delta=0.5)
                self.assertAlmostEqual(
                    abs(result["deflection"]["maximum"]["deflection_mm"]),
                    deflection_mm, delta=0.05)

    def test_two_span_support_moment(self):
        # Two equal spans with uniform load: M_support = wL^2/8.
        w = 10.0*G
        for name, result in solvers(beam(10000, [0, 5000, 10000],
                                         mass=100.0)):
            with self.subTest(solver=name):
                at_support = [
                    abs(end["My_nm"]) for element in result["element_forces"]
                    for end, station in ((element["i"],
                                          element["start_station_mm"]),
                                         (element["j"],
                                          element["end_station_mm"]))
                    if station is not None and abs(station-5000.0) < 1.0]
                self.assertTrue(at_support)
                for value in at_support:
                    self.assertAlmostEqual(value, w*5.0**2/8.0, delta=0.5)


class ReferenceSolverTests(unittest.TestCase):
    def assert_matches_reference(self, length_mm, supports, mass=0.0,
                                 points=()):
        stations = sorted({0.0, float(length_mm)} | set(map(float, supports)) |
                          {float(station) for station, _ in points})
        stations_m = [value/1000.0 for value in stations]
        index = {value: position for position, value in enumerate(stations)}
        expected, _ = solve_beam(
            stations_m, [index[float(value)] for value in supports],
            [EI]*(len(stations)-1), mass/(length_mm/1000.0)*G,
            {index[float(station)]: value*G for station, value in points})
        for name, result in solvers(beam(length_mm, supports, mass, points)):
            with self.subTest(solver=name):
                signed = by_id(result, "unconstrained_reaction_mass_kg")
                for support_id, value in zip(
                        ("H%d" % (k+1) for k in range(len(supports))),
                        expected):
                    self.assertAlmostEqual(signed[support_id], value/G,
                                           delta=0.02)

    def test_unequal_spans_mixed_load(self):
        self.assert_matches_reference(
            11000, [0, 3000, 8000, 11000], mass=110.0,
            points=[(1500, 50.0), (6000, 120.0), (9500, 80.0)])

    def test_closely_spaced_supports(self):
        self.assert_matches_reference(
            10000, [0, 4990, 5010, 10000], mass=100.0)

    def test_many_supports_with_point_loads(self):
        supports = [0, 1500, 3500, 4000, 6500, 9000, 11000, 12500, 15000, 18000]
        self.assert_matches_reference(
            18000, supports, mass=180.0,
            points=[(2500, 200.0), (7000, 90.0), (16500, 150.0)])


class TensionOnlyRedistributionTests(unittest.TestCase):
    def test_several_uplift_supports_redistribute_consistently(self):
        # Heavy load in one end bay lifts several hoists; releasing one
        # changes the sign at its neighbours.  Both solvers must reach the
        # same complementarity-valid state.
        item = beam(16000, [0, 2000, 4000, 7000, 10000, 13000, 16000],
                    mass=40.0, points=[(1000, 600.0), (15000, 40.0)])
        results = dict(solvers(item))
        reference = by_id(results["continuous_beam"])
        general = by_id(results["general_frame"])
        for support_id, value in reference.items():
            self.assertAlmostEqual(general[support_id], value, delta=0.05)
        for name, result in results.items():
            with self.subTest(solver=name):
                signed = by_id(result, "unconstrained_reaction_mass_kg")
                self.assertTrue(any(value < 0 for value in signed.values()))
                released = [item for item in result["reactions"]
                            if not item["support_active"]]
                self.assertTrue(released)
                self.assertTrue(all(item["reaction_mass_kg"] >= -1.0e-6
                                    for item in result["reactions"]))
                self.assertAlmostEqual(sum(by_id(result).values()), 680.0,
                                       delta=0.05)


if __name__ == "__main__":
    unittest.main()
