import unittest

from rigcalc.model import DocumentModel, Point3D, PointLoad, Support, TrussSegment
from rigcalc.topology import build_constructions


class AttachmentTests(unittest.TestCase):
    def test_support_projects_to_station(self):
        start, end = Point3D(0, 0), Point3D(9000, 0)
        truss = TrussSegment("T1", "", "Line", start, 9000, start, end)
        support = Support("H1", "H001", Point3D(644, 0))
        construction = build_constructions(DocumentModel([truss], [support]))[0]
        self.assertAlmostEqual(construction.supports[0].attachment.global_station_mm, 644)

    def test_load_outside_search_sphere_remains_unassigned(self):
        start, end = Point3D(0, 0, 5000), Point3D(9000, 0, 5000)
        truss = TrussSegment("T1", "", "Line", start, 9000, start, end)
        load = PointLoad("L1", "Load", Point3D(4500, 0, 6000), "Lighting Device", 10)
        document = DocumentModel(trusses=[truss], point_loads=[load])
        construction = build_constructions(document)[0]
        self.assertEqual(construction.point_loads, [])
        self.assertEqual(document.unassigned_point_loads, [load])

    def test_load_inside_3d_sphere_attaches_with_evidence(self):
        start, end = Point3D(0, 0, 5000), Point3D(9000, 0, 5000)
        truss = TrussSegment("T1", "", "Line", start, 9000, start, end)
        load = PointLoad("L1", "Load", Point3D(4500, 0, 5040), "Lighting Device", 10)
        document = DocumentModel(trusses=[truss], point_loads=[load])
        construction = build_constructions(document)[0]
        attachment = construction.point_loads[0].attachment
        self.assertAlmostEqual(attachment.distance_from_truss_axis_mm, 40)
        self.assertEqual(attachment.method, "geometry_sphere")
        self.assertEqual(attachment.confidence, "EXACT")

    def test_truss_envelope_turns_chord_surface_into_exact_hit(self):
        start, end = Point3D(0, 0, 5000), Point3D(9000, 0, 5000)
        truss = TrussSegment(
            "T1", "", "Line", start, 9000, start, end,
            width_mm=290, height_mm=290)
        load = PointLoad("L1", "Load", Point3D(4500, 0, 5145), "Lighting Device", 10)
        document = DocumentModel(trusses=[truss], point_loads=[load])
        attachment = build_constructions(document)[0].point_loads[0].attachment
        self.assertAlmostEqual(attachment.distance_from_truss_axis_mm, 145)
        self.assertAlmostEqual(attachment.carrier_clearance_mm, 0)
        self.assertEqual(attachment.confidence, "EXACT")

    def test_support_uuid_has_priority_over_geometry(self):
        start, end = Point3D(0, 0), Point3D(3000, 0)
        truss = TrussSegment(
            "T1", "", "Line", start, 3000, start, end,
            vw_connections={"start": "connection-1"})
        support = Support(
            "H1", "Hoist", Point3D(1000, 0),
            vw_truss_system="connection-1")
        document = DocumentModel(trusses=[truss], supports=[support])
        attachment = build_constructions(document)[0].supports[0].attachment
        self.assertEqual(attachment.method, "explicit_system_3d_geometry")
        self.assertAlmostEqual(attachment.global_station_mm, 1000)

    def test_support_uuid_does_not_override_impossible_3d_geometry(self):
        start, end = Point3D(0, 0, 5000), Point3D(3000, 0, 5000)
        truss = TrussSegment(
            "T1", "", "Line", start, 3000, start, end,
            vw_connections={"start": "connection-1"})
        support = Support(
            "H1", "Hoist", Point3D(1000, 0, 0),
            vw_truss_system="connection-1")
        document = DocumentModel(trusses=[truss], supports=[support])
        construction = build_constructions(document)[0]
        self.assertEqual(construction.supports, [])
        self.assertEqual(document.unassigned_supports, [support])

    def test_explicit_uuid_resolves_inclined_truss_with_plan_geometry(self):
        start = Point3D(0, 0, 1000)
        end = Point3D(3000, 0, 5000)
        truss = TrussSegment(
            "T1", "", "Line", start, 5000, start, end,
            vw_connections={"start": "connection-1"})
        support = Support(
            "H1", "Hoist", Point3D(1500, 20, 0),
            vw_truss_system="connection-1")
        document = DocumentModel(trusses=[truss], supports=[support])
        attachment = build_constructions(document)[0].supports[0].attachment
        self.assertEqual(
            attachment.method, "explicit_system_inclined_plan_geometry")
        self.assertAlmostEqual(attachment.global_station_mm, 2500.0)
        self.assertEqual(attachment.confidence, "EXACT")

    def test_stale_uuid_uses_unique_exact_inclined_plan_hit(self):
        start = Point3D(0, 0, 1000)
        end = Point3D(3000, 0, 5000)
        truss = TrussSegment("T1", "", "Line", start, 5000, start, end)
        support = Support(
            "H1", "Hoist", Point3D(1500, 0, 0),
            vw_truss_system="stale-uuid")
        document = DocumentModel(trusses=[truss], supports=[support])
        attachment = build_constructions(document)[0].supports[0].attachment
        self.assertEqual(
            attachment.method, "unresolved_system_inclined_plan_geometry")
        self.assertEqual(attachment.confidence, "INFERRED")

    def test_stale_uuid_inclined_plan_crossing_remains_unassigned(self):
        first = TrussSegment(
            "T1", "", "Line", Point3D(0, 0, 1000), 5000,
            Point3D(0, 0, 1000), Point3D(3000, 0, 5000))
        second = TrussSegment(
            "T2", "", "Line", Point3D(1500, -1500, 8000), 5000,
            Point3D(1500, -1500, 8000), Point3D(1500, 1500, 12000))
        support = Support(
            "H1", "Hoist", Point3D(1500, 0, 0),
            vw_truss_system="stale-uuid")
        document = DocumentModel(trusses=[first, second], supports=[support])
        build_constructions(document)
        self.assertEqual(document.unassigned_supports, [support])


if __name__ == "__main__":
    unittest.main()
