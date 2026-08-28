import unittest

from rigcalc.normalization import load_components, normalize_inventory, parse_number


class NormalizationTests(unittest.TestCase):
    def test_locale_number_and_unit_are_parsed(self):
        self.assertAlmostEqual(parse_number("29,94 kg"), 29.94)

    def test_bare_unknown_weight_is_not_assumed_to_be_kg(self):
        self.assertEqual(load_components("Unknown PIO", {"Weight": "50000"}), [])

    def test_generic_internal_weight_is_converted_from_grams(self):
        components = load_components("BrxGenericWeight", {"Weight": "50000"})
        self.assertEqual(components[0]["mass_kg"], 50.0)
        self.assertEqual(components[0]["source_field"], "Weight")

    def test_distributed_load_retains_rate_length_and_total(self):
        component = load_components("BrxDistributedWeight", {
            "TotalWeight": "213252,5", "DistWeight": "100",
            "Lenght": "2132,525",
        })[0]
        self.assertAlmostEqual(component["mass_kg"], 213.2525)
        self.assertEqual(component["mass_per_m_kg"], 100.0)
        self.assertAlmostEqual(component["length_mm"], 2132.525)

    def test_soft_goods_is_always_a_distributed_load(self):
        component = load_components("Soft Goods", {
            "WeightKG": "45,37114508",
            "DistWeightKG": "15,87",
            "AdjustableLength": "2,85892533597916e03",
        })[0]
        self.assertEqual(component["kind"], "distributed")
        self.assertAlmostEqual(component["mass_kg"], 45.37114508)
        self.assertAlmostEqual(component["mass_per_m_kg"], 15.87)
        self.assertAlmostEqual(component["length_mm"], 2858.92533597916)

    def test_uuid_connection_resolves_to_truss_and_port(self):
        inventory = [
            {
                "scan_id": "P001", "parametric_record": "TrussItem",
                "parametric_fields": {
                    "Name": "Truss", "TrussSystem": "T1",
                    "C_START_UUID": "uuid-1",
                },
            },
            {
                "scan_id": "P002", "parametric_record": "BrxHoist",
                "parametric_fields": {
                    "HoistName": "Hoist", "WeightWithChain": "12020",
                    "TrussSysBottom": "uuid-1",
                },
            },
        ]
        normalized = normalize_inventory(inventory)
        hoist = normalized["objects"][1]
        self.assertEqual(hoist["load_components"][0]["mass_kg"], 12.02)
        resolved = hoist["explicit_connections"][0]["resolved"]
        self.assertEqual(resolved["truss_scan_id"], "P001")
        self.assertEqual(resolved["port"], "C_START_UUID")
        self.assertEqual(normalized["summary"]["unresolved_connection_count"], 0)

    def test_nested_weight_is_flagged_for_double_counting_review(self):
        normalized = normalize_inventory([{
            "scan_id": "P010", "parametric_record": "Speaker",
            "parent_scan_id": "P009", "parametric_fields": {"BxWeightKG": "19,96"},
        }])
        self.assertIn("nested_object_check_double_counting", normalized["objects"][0]["issues"])

    def test_layer_scope_and_hanging_position_association_are_explicit(self):
        inventory = [{
            "scan_id": "P001", "parametric_record": "Lighting Device",
            "layer_name": "Lights floor",
            "parametric_fields": {"Weight": "10 kg", "Position": "LX1"},
        }, {
            "scan_id": "P002", "parametric_record": "Light Position Obj",
            "layer_name": "Rigging",
            "parametric_fields": {"Position Name": "LX1"},
        }]
        normalized = normalize_inventory(inventory, included_layers=["Rigging"])
        light, position = normalized["objects"]
        self.assertEqual(light["scope"]["status"], "excluded")
        self.assertEqual(light["associations"][0]["value"], "LX1")
        self.assertEqual(position["category"], "hanging_position")
        self.assertEqual(position["associations"][0]["role"], "definition")
        self.assertEqual(normalized["summary"]["included_object_count"], 1)
        self.assertEqual(normalized["summary"]["excluded_object_count"], 1)

    def test_connection_to_unselected_truss_is_flagged(self):
        inventory = [{
            "scan_id": "P001", "parametric_record": "TrussItem",
            "layer_name": "Structure excluded",
            "parametric_fields": {"C_START_UUID": "u1", "TrussSystem": "T1"},
        }, {
            "scan_id": "P002", "parametric_record": "BrxHoist",
            "layer_name": "Rigging included",
            "parametric_fields": {"TrussSysBottom": "u1", "WeightWithChain": "10000"},
        }]
        normalized = normalize_inventory(inventory, included_layers=["Rigging included"])
        self.assertIn(
            "connection_target_outside_scope", normalized["objects"][1]["issues"])

    def test_unresolved_explicit_connection_is_visible(self):
        normalized = normalize_inventory([{
            "scan_id": "P001", "parametric_record": "BrxHoist",
            "parametric_fields": {
                "TrussSysBottom": "missing", "WeightWithChain": "10000"},
        }])
        self.assertIn(
            "unresolved_explicit_connection", normalized["objects"][0]["issues"])

    def test_dead_hang_drop_retains_weight_top_uuid_and_bottom_requirement(self):
        normalized = normalize_inventory([{
            "scan_id": "P001", "parametric_record": "BridleObj",
            "parametric_fields": {
                "AsDrop": "True", "BridleType": "DeadHang",
                "TotalWeight": "6550", "HouseRiggingPoint1": "top-1",
            },
        }])
        item = normalized["objects"][0]
        self.assertEqual(item["category"], "dead_hang")
        self.assertEqual(item["load_components"][0]["mass_kg"], 6.55)
        self.assertEqual(item["explicit_connections"][0]["role"], "top")
        self.assertIn("requires_geometric_bottom_attachment", item["issues"])


if __name__ == "__main__":
    unittest.main()
