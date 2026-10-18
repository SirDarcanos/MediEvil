"""Transport/lifecycle examples; synthetic fixtures are not live-emulator evidence."""
import unittest
from unittest.mock import patch
import ram
from test_minimap import fixture, FakeRAM


class DuckDiscoveryTests(unittest.TestCase):
    def duck_tracker(self, data=None, redux=(), duck=(73,)):
        class FakeDuck(FakeRAM):
            pass
        FakeDuck.data = fixture() if data is None else data
        for replacement in (patch('ram.redux_pids', return_value=list(redux)),
                            patch('ram.duckstation_pids', return_value=list(duck), create=True),
                            patch('ram.SharedRAM', FakeRAM),
                            patch('ram.DuckStationRAM', FakeDuck, create=True)):
            replacement.start()
            self.addCleanup(replacement.stop)
        tracker = ram.Tracker()
        self.addCleanup(tracker.close)
        return tracker

    def test_auto_detects_duckstation_and_preserves_raw_position(self):
        sample = self.duck_tracker().sample()
        self.assertEqual(sample['status'], 'live')
        self.assertEqual(sample['emulator'], 'duckstation')
        self.assertEqual(sample['pid'], 73)
        self.assertEqual(sample['position'], [-32000, -200000, 32000])

    def test_mixed_emulators_require_explicit_selection(self):
        sample = self.duck_tracker(redux=(42,)).sample()
        self.assertEqual(sample['status'], 'multiple')
        self.assertNotIn('position', sample)

    def test_disabling_export_does_not_leave_an_old_paused_marker(self):
        tracker = self.duck_tracker()
        with patch('ram.time.monotonic', return_value=10):
            self.assertEqual(tracker.sample()['status'], 'live')
        # A mapped view can outlive its producer's export. When the frame is
        # stalled, close/reopen the named object to verify it is still exported.
        with patch('ram.DuckStationRAM', side_effect=OSError('export removed')):
            with patch('ram.time.monotonic', return_value=12):
                sample = tracker.sample()
        self.assertEqual(sample['status'], 'unavailable')
        self.assertNotIn('position', sample)

    def test_wrong_disc_does_not_expose_a_marker(self):
        sample = self.duck_tracker(data=bytes(ram.RAM_SIZE)).sample()
        self.assertEqual(sample['status'], 'waiting_game')
        self.assertNotIn('position', sample)


if __name__ == '__main__':
    unittest.main(verbosity=2)
