import unittest

from rigcalc.vw.records import safe_float


class SafeFloatTests(unittest.TestCase):
    def test_parses_finite_values_and_known_units(self):
        self.assertEqual(safe_float("12,5 kg"), 12.5)

    def test_rejects_nonfinite_values(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            self.assertEqual(safe_float(value, 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
