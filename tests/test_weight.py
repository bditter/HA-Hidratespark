"""16-bit weight decoding, auto-calibration, and weight-based fill tracking."""

import unittest

from ha_stub import HomeAssistant, load_state, local_ts

state = load_state()
Sip = state.Sip


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

    def test_explicit_full_empty_calibration_sets_per_bottle_scale(self):
        b = new_bottle(887)
        b.update_fill_from_weight(34656)
        self.assertTrue(b.calibrate_full())
        b.update_fill_from_weight(33500)
        self.assertTrue(b.calibrate_empty())

        self.assertEqual(b.weight_full_raw, 34656)
        self.assertEqual(b.weight_empty_raw, 33500)
        self.assertAlmostEqual(b.raw_units_per_ml, (34656 - 33500) / 887)

        b.update_fill_from_weight(33500 + (34656 - 33500) // 2)
        self.assertAlmostEqual(b.current_fill_ml, 887 / 2, delta=2)

    def test_calibration_buttons_need_a_stable_raw_weight(self):
        b = new_bottle(887)
        self.assertFalse(b.calibrate_full())
        self.assertFalse(b.calibrate_empty())

    def test_weight_jump_back_to_full_counts_refill(self):
        b = new_bottle(887)
        b.update_fill_from_weight(34656)
        b.calibrate_full()
        b.update_fill_from_weight(33500)
        b.calibrate_empty()

        b.update_fill_from_weight(34656)

        self.assertEqual(b.current_fill_ml, 887)
        self.assertEqual(b.refills_today, 1)

    def test_small_weight_increase_does_not_count_refill(self):
        b = new_bottle(887)
        b.update_fill_from_weight(34656)
        b.calibrate_full()
        b.update_fill_from_weight(33500)
        b.calibrate_empty()
        b.update_fill_from_weight(33550)

        self.assertEqual(b.refills_today, 0)

    def test_tiny_weight_jitter_does_not_move_fill(self):
        b = new_bottle(887)
        b.update_fill_from_weight(35041)
        b.calibrate_full()
        b.update_fill_from_weight(33576)
        b.calibrate_empty()
        b.update_fill_from_weight(33576 + 100)
        fill = b.current_fill_ml

        self.assertFalse(b.update_fill_from_weight(33576 + 103))
        self.assertEqual(b.current_fill_ml, fill)
        self.assertTrue(b.update_fill_from_weight(33576 + 110))
        self.assertGreater(b.current_fill_ml, fill)

    def test_calibrated_weight_drop_counts_consumption_instead_of_sip_volume(self):
        b = new_bottle(887)
        b.update_fill_from_weight(35066)
        b.calibrate_full()
        b.update_fill_from_weight(33576)
        b.calibrate_empty()
        b.update_fill_from_weight(35066)
        b.reset_totals()

        b.add_sip(
            Sip(
                timestamp=local_ts(2026, 6, 18, 12, 0),
                volume_ml=62,
                reported_total_ml=100,
            )
        )
        self.assertEqual(b.total_today_ml, 0)
        self.assertEqual(b.lifetime_total_ml, 0)
        self.assertEqual(b.sips_today, 1)

        b.update_fill_from_weight(33576)

        self.assertEqual(b.current_fill_ml, 0)
        self.assertEqual(b.total_today_ml, 887)
        self.assertEqual(b.lifetime_total_ml, 887)

    def test_partial_fill_uses_raw_position_without_snapping_full(self):
        b = new_bottle(887)
        b.update_fill_from_weight(35066)
        b.calibrate_full()
        b.update_fill_from_weight(33576)
        b.calibrate_empty()
        b.update_fill_from_weight(35066)
        b.reset_totals()

        b.update_fill_from_weight(35051)

        self.assertLess(b.current_fill_ml, 887)
        self.assertEqual(b.current_fill_pct, 99)

    def test_near_empty_raw_snaps_to_zero(self):
        b = new_bottle(887)
        b.update_fill_from_weight(35066)
        b.calibrate_full()
        b.update_fill_from_weight(33576)
        b.calibrate_empty()
        b.update_fill_from_weight(35066)

        b.update_fill_from_weight(33579)

        self.assertEqual(b.current_fill_ml, 0)
        self.assertEqual(b.current_fill_pct, 0)

    def test_reset_rebaselines_fill_from_latest_raw_weight(self):
        b = new_bottle(887)
        b.update_fill_from_weight(35066)
        b.calibrate_full()
        b.update_fill_from_weight(33576)
        b.calibrate_empty()
        b.update_fill_from_weight(35066)
        b.update_fill_from_weight(33576)

        b.reset_totals()
        self.assertEqual(b.current_fill_ml, 0)

        b.update_fill_from_weight(34984)

        self.assertEqual(b.current_fill_pct, 94)
        self.assertEqual(b.total_today_ml, 0)
        self.assertEqual(b.lifetime_total_ml, 0)

    def test_weight_refill_counts_once_while_fill_is_climbing(self):
        b = new_bottle(887)
        b.update_fill_from_weight(35066)
        b.calibrate_full()
        b.update_fill_from_weight(33576)
        b.calibrate_empty()
        b.reset_totals()

        b.update_fill_from_weight(34300)
        b.update_fill_from_weight(34984)
        b.update_fill_from_weight(35066)

        self.assertEqual(b.refills_today, 1)
        self.assertEqual(b.total_today_ml, 0)

    def test_empty_to_fill_line_counts_each_refill_cycle(self):
        b = new_bottle(887)
        b.update_fill_from_weight(35066)
        b.calibrate_full()
        b.update_fill_from_weight(33576)
        b.calibrate_empty()
        self.assertTrue(b.refill_detector_armed)
        b.update_fill_from_weight(35066)
        b.reset_totals()

        b.update_fill_from_weight(33576)
        self.assertTrue(b.refill_detector_armed)
        b.update_fill_from_weight(34984)
        self.assertFalse(b.refill_detector_armed)
        b.update_fill_from_weight(33576)
        b.update_fill_from_weight(34984)

        self.assertEqual(b.refills_today, 2)
        self.assertGreater(b.total_today_ml, 1700)

    def test_reset_totals_keeps_fill_and_calibration(self):
        b = new_bottle(887)
        b.update_fill_from_weight(34656)
        b.calibrate_full()
        b.update_fill_from_weight(33500)
        b.calibrate_empty()
        b.add_sip(Sip(timestamp=0, volume_ml=100, reported_total_ml=100))
        b.update_fill_from_weight(34656)

        b.reset_totals()

        self.assertEqual(b.total_today_ml, 0)
        self.assertEqual(b.lifetime_total_ml, 0)
        self.assertEqual(b.sips_today, 0)
        self.assertEqual(b.refills_today, 0)
        self.assertIsNone(b.last_sip)
        self.assertIsNone(b.last_reported_total_ml)
        self.assertEqual(b.current_fill_ml, 887)
        self.assertEqual(b.weight_full_raw, 34656)
        self.assertEqual(b.weight_empty_raw, 33500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
