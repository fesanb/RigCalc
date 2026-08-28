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


if __name__ == "__main__":
    unittest.main()
