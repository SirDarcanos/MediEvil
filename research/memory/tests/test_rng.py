import unittest
from tools.analyze_rng import step, analyze


class RngTests(unittest.TestCase):
    def test_known_steps_and_unsigned_wrap(self):
        self.assertEqual(step(0), (12345, 0))
        self.assertEqual(step(1), (1103527590, 16838))
        state, output = step(0xffffffff)
        self.assertTrue(0 <= state <= 0xffffffff)
        self.assertEqual(output, (state >> 16) & 32767)

    def row(self, before, frame=1):
        after, output = step(before)
        return dict(before=before, afterRegister=after, output=output, frame=frame,
                    callerRA=0x80012348, submode=0)

    def test_validate_actual_register_steps(self):
        first = self.row(123)
        result = analyze([first, self.row(first['afterRegister'], 2)])
        self.assertEqual(result['validated_native_steps'], 2)
        self.assertEqual(result['state_discontinuities'], [])

    def test_reseeding_is_reported_not_hidden(self):
        result = analyze([self.row(123), self.row(999, 2)])
        self.assertEqual(len(result['state_discontinuities']), 1)

    def test_reject_incorrect_callback_observation(self):
        row = self.row(123)
        row['afterRegister'] ^= 1
        with self.assertRaises(ValueError):
            analyze([row])
        with self.assertRaises(ValueError):
            analyze([])


if __name__ == '__main__':
    unittest.main()
