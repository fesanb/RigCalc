import unittest

from rigcalc.vw.hoist_fields import high_hook_field_values


class HoistFieldTests(unittest.TestCase):
    def test_high_hook_mass_is_converted_to_vectorworks_units(self):
        values = high_hook_field_values(100.0)
        self.assertEqual(values["ReactionForceWeight"], "100000.000000")
        self.assertEqual(values["ReactionForce"], "980.665000")


if __name__ == "__main__":
    unittest.main()
