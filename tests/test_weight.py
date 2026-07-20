"""16-bit weight decoding, auto-calibration, and weight-based fill tracking."""

import unittest

from ha_stub import HomeAssistant, load_state

state = load_state()


def new_bottle(size=946):
    return state.BottleState(HomeAssistant(), "entry", size)


class WeightCalibrationTest(unittest.TestCase):
    def test_first_reading_calibrates_full_anchor(self):
        b = new_bottle(946)
        changed = b.update_fill_from_weight(37000)
        self.assertTrue(changed)
        self.assertEqual(b.weight_full_raw, 37000)
        self.assertEqual(b.current_fill_ml, 946)

    def test_empty_bottle_reads_zero(self):
        # Measured full+empty calibration on a 946 mL bottle.
        b = new_bottle(946)
        b.update_fill_from_weight(37115)  # full anchor
        self.assertEqual(b.current_fill_ml, 946)
        b.update_fill_from_weight(35880)  # truly empty
        self.assertAlmostEqual(b.current_fill_ml, 0, delta=20)

    def test_fill_tracks_proportionally(self):
        b = new_bottle(946)
        b.update_fill_from_weight(37115)  # full
        # halfway down the raw span (1235 units) -> ~half the bottle drunk
        b.update_fill_from_weight(37115 - 1235 // 2)
        self.assertAlmostEqual(b.current_fill_ml, 473, delta=15)

    def test_fill_never_exceeds_full_or_goes_negative(self):
        b = new_bottle(946)
        b.update_fill_from_weight(37000)
        b.update_fill_from_weight(99000)  # implausibly heavy
        self.assertEqual(b.current_fill_ml, 946)
        b.update_fill_from_weight(0)  # implausibly light
        self.assertEqual(b.current_fill_ml, 0)

    def test_empty_reads_zero_after_a_partial_refill(self):
        # The key tare-anchoring win: once a real drain establishes the empty
        # floor, empty reads 0 even when a later fill doesn't reach the brim.
        b = new_bottle(946)
        b.update_fill_from_weight(37115)  # full anchor
        b.update_fill_from_weight(35880)  # drained to empty -> learns the tare
        self.assertAlmostEqual(b.current_fill_ml, 0, delta=20)
        # Refill only part-way (anchor moves, tare must not).
        b.refill("cap_close", 36800)
        b.update_fill_from_weight(36800)  # ~partial fill
        self.assertGreater(b.current_fill_ml, 600)
        self.assertLess(b.current_fill_ml, 800)
        # Drink it all again: still reads ~0, no phantom residual.
        b.update_fill_from_weight(35882)
        self.assertAlmostEqual(b.current_fill_ml, 0, delta=20)

    def test_calibration_is_not_a_refill_but_cap_close_is(self):
        b = new_bottle(946)
        b.refill("calibration", 37000)
        self.assertEqual(b.refills_today, 0, "calibration must not count as a refill")
        b.refill("cap_close", 37100)
        self.assertEqual(b.refills_today, 1, "a real refill increments the counter")


if __name__ == "__main__":
    unittest.main(verbosity=2)
