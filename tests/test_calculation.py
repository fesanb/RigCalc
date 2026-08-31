import unittest

from rigcalc.model import (AttachedObject, Attachment, Construction, DocumentModel,
                           Point3D, PointLoad, Support, TrussSegment)
from rigcalc.solver import calculate_reactions
from rigcalc.topology import build_constructions


class CalculationTests(unittest.TestCase):
    def test_two_support_reactions_include_truss_and_point_mass(self):
        start, end = Point3D(0, 0), Point3D(10000, 0)
        truss = TrussSegment(
            "T1", "Truss", "Line", start, 10000, start, end,
            self_weight_kg=100)
        left = Support(
            "H1", "Left", Point3D(0, 0), weight_with_chain_kg=10,
            capacity_kg=500)
        right = Support(
            "H2", "Right", Point3D(10000, 0), weight_with_chain_kg=10,
            capacity_kg=500)
        load = PointLoad(
            "L1", "Load", Point3D(2500, 0), "Lighting Device", 100)
        document = DocumentModel(
            trusses=[truss], supports=[left, right], point_loads=[load])
        constructions = build_constructions(document)
        result = calculate_reactions(document, constructions)["constructions"][0]
        self.assertEqual(result["status"], "preliminary")
        self.assertAlmostEqual(result["total_applied_mass_kg"], 200)
        self.assertAlmostEqual(result["reactions"][0]["reaction_mass_kg"], 125)
        self.assertAlmostEqual(result["reactions"][1]["reaction_mass_kg"], 75)
        self.assertAlmostEqual(
            result["reactions"][0]["preliminary_high_hook_mass_kg"], 135)
        self.assertTrue(result["validation"]["calculated"])
        self.assertTrue(result["validation"]["equilibrium_valid"])
        self.assertTrue(result["validation"]["support_model_valid"])
        self.assertTrue(result["load_transfer_eligible"])

    def test_configured_cable_rate_is_applied_over_each_truss_length(self):
        start, end = Point3D(0, 0), Point3D(10000, 0)
        truss = TrussSegment(
            "T1", "Truss", "Line", start, 10000, start, end,
            cable_load_kg_m=2.0)
        document = DocumentModel(
            trusses=[truss],
            supports=[Support("H1", "", start), Support("H2", "", end)])
        result = calculate_reactions(
            document, build_constructions(document))["constructions"][0]
        cable = next(item for item in result["loads"]
                     if item["source_type"] == "cable_flat_rate")
        self.assertAlmostEqual(cable["mass_kg"], 20.0)
        self.assertAlmostEqual(cable["mass_per_m_kg"], 2.0)
        self.assertAlmostEqual(result["total_applied_mass_kg"], 20.0)

    def test_multi_support_solver_requires_mechanical_section(self):
        start, end = Point3D(0, 0), Point3D(10000, 0)
        truss = TrussSegment(
            "T1", "Truss", "Line", start, 10000, start, end,
            self_weight_kg=100)
        supports = [
            Support("H1", "", Point3D(0, 0)),
            Support("H2", "", Point3D(5000, 0)),
            Support("H3", "", Point3D(10000, 0)),
        ]
        document = DocumentModel(trusses=[truss], supports=supports)
        constructions = build_constructions(document)
        result = calculate_reactions(document, constructions)["constructions"][0]
        self.assertEqual(result["status"], "not_calculated")
        self.assertTrue(any(issue.startswith("mechanical_section_missing")
                            for issue in result["issues"]))

    def test_high_hook_load_is_transferred_to_supporting_construction(self):
        def attachment(station):
            return Attachment("T", "Truss", 0, station, station, station, 0)

        lower = Construction(
            "LOWER", [], [], "open_chain",
            supports=[
                AttachedObject(Support(
                    "LH1", "", Point3D(0, 0), weight_with_chain_kg=10,
                    transfer_target_construction_id="UPPER",
                    transfer_target_station_mm=2500), attachment(0)),
                AttachedObject(Support(
                    "LH2", "", Point3D(10000, 0), weight_with_chain_kg=10),
                               attachment(10000)),
            ],
            point_loads=[AttachedObject(
                PointLoad("LOAD", "", Point3D(5000, 0), "Load", 100),
                attachment(5000))],
        )
        upper = Construction(
            "UPPER", [], [], "open_chain",
            supports=[
                AttachedObject(Support("UH1", "", Point3D(0, 0)), attachment(0)),
                AttachedObject(Support("UH2", "", Point3D(10000, 0)),
                               attachment(10000)),
            ],
        )
        result = calculate_reactions(
            DocumentModel(), [upper, lower])["constructions"]
        by_id = {item["construction_id"]: item for item in result}
        transferred = by_id["UPPER"]["loads"][0]
        self.assertEqual(transferred["source_type"], "transferred_high_hook_load")
        self.assertAlmostEqual(transferred["mass_kg"], 60)
        self.assertAlmostEqual(by_id["UPPER"]["reactions"][0]["reaction_mass_kg"], 45)
        self.assertAlmostEqual(by_id["UPPER"]["reactions"][1]["reaction_mass_kg"], 15)

    def test_uplift_result_is_not_transferred_to_another_construction(self):
        def attachment(station):
            return Attachment("T", "Truss", 0, station, station, station, 0)

        lower = Construction(
            "LOWER", [], [], "open_chain",
            supports=[
                AttachedObject(Support(
                    "LH1", "", Point3D(2000, 0),
                    transfer_target_construction_id="UPPER",
                    transfer_target_station_mm=2500), attachment(2000)),
                AttachedObject(Support("LH2", "", Point3D(8000, 0)),
                               attachment(8000)),
            ],
            point_loads=[AttachedObject(
                PointLoad("LOAD", "", Point3D(10000, 0), "Load", 120),
                attachment(10000))],
        )
        upper = Construction(
            "UPPER", [], [], "open_chain",
            supports=[
                AttachedObject(Support("UH1", "", Point3D(0, 0)), attachment(0)),
                AttachedObject(Support("UH2", "", Point3D(10000, 0)),
                               attachment(10000)),
            ],
        )
        result = calculate_reactions(
            DocumentModel(), [upper, lower])["constructions"]
        by_id = {item["construction_id"]: item for item in result}
        self.assertFalse(by_id["LOWER"]["load_transfer_eligible"])
        self.assertFalse(any(item["source_type"] == "transferred_high_hook_load"
                             for item in by_id["UPPER"]["loads"]))
        self.assertIn("upstream_load_transfer_ineligible:LOWER",
                      by_id["UPPER"]["issues"])

    def test_cyclic_load_transfer_fails_closed_for_every_cycle_member(self):
        def attachment(station):
            return Attachment("T", "Truss", 0, station, station, station, 0)

        def item(identifier, target):
            return Construction(
                identifier, [], [], "open_chain",
                supports=[
                    AttachedObject(Support(
                        identifier + "H1", "", Point3D(0, 0),
                        transfer_target_construction_id=target,
                        transfer_target_station_mm=5000), attachment(0)),
                    AttachedObject(Support(identifier + "H2", "", Point3D(10000, 0)),
                                   attachment(10000)),
                ],
                point_loads=[AttachedObject(
                    PointLoad(identifier + "L", "", Point3D(5000, 0), "Load", 100),
                    attachment(5000))],
            )

        for links in (("A", "B"), ("B", "A")), (("A", "B"),
                                                     ("B", "C"),
                                                     ("C", "A")):
            with self.subTest(links=links):
                result = calculate_reactions(
                    DocumentModel(), [item(identifier, target)
                                      for identifier, target in links])["constructions"]
                for construction in result:
                    self.assertEqual(construction["status"], "not_calculated")
                    self.assertFalse(construction["load_transfer_eligible"])
                    self.assertIn("cyclic_load_transfer_graph", construction["issues"])
                    self.assertFalse(any(
                        load["source_type"] == "transferred_high_hook_load"
                        for load in construction["loads"]))

    def test_multi_level_load_transfer_requires_each_upstream_result(self):
        def attachment(station):
            return Attachment("T", "Truss", 0, station, station, station, 0)

        def construction(identifier, target=None, load_mass=0):
            support = Support(identifier + "H1", "", Point3D(0, 0),
                              weight_with_chain_kg=10,
                              transfer_target_construction_id=target,
                              transfer_target_station_mm=5000)
            return Construction(
                identifier, [], [], "open_chain",
                supports=[AttachedObject(support, attachment(0)),
                          AttachedObject(Support(identifier + "H2", "", Point3D(10000, 0)),
                                         attachment(10000))],
                point_loads=([AttachedObject(
                    PointLoad(identifier + "L", "", Point3D(5000, 0),
                              "Load", load_mass), attachment(5000))]
                             if load_mass else []),
            )

        lower = construction("LOWER", "MIDDLE", 100)
        middle = construction("MIDDLE", "UPPER")
        upper = construction("UPPER")
        result = calculate_reactions(
            DocumentModel(), [upper, middle, lower])["constructions"]
        by_id = {item["construction_id"]: item for item in result}
        middle_transfer = next(load for load in by_id["MIDDLE"]["loads"]
                               if load["source_type"] == "transferred_high_hook_load")
        upper_transfer = next(load for load in by_id["UPPER"]["loads"]
                              if load["source_type"] == "transferred_high_hook_load")
        self.assertAlmostEqual(middle_transfer["mass_kg"], 60.0)
        self.assertAlmostEqual(upper_transfer["mass_kg"], 40.0)


if __name__ == "__main__":
    unittest.main()
