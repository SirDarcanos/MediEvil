from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import analyze


class ScanTests(unittest.TestCase):
    def test_full_range_unaligned_and_changes_that_revert(self):
        with tempfile.TemporaryDirectory() as directory:
            original = bytearray(analyze.RAM_SIZE)
            modified = original.copy()
            for index in (0, 3, 4096, analyze.RAM_SIZE-1):
                modified[index] = 255
            paths = [Path(directory)/str(i) for i in range(3)]
            for path, data in zip(paths, (original, modified, original)):
                path.write_bytes(data)
            result = analyze.compare_all(paths)
            self.assertEqual(result['capture_count'], 3)
            self.assertEqual(result['changed_bytes'], 4)
            self.assertEqual(sum(result['changed_bytes_by_4KiB']), 4)
            self.assertEqual(result['changed_bytes_by_4KiB'][0], 2)
            self.assertEqual(result['changed_bytes_by_4KiB'][-1], 1)

    def test_reject_missing_or_single_capture(self):
        with self.assertRaisesRegex(ValueError, 'at least two'):
            analyze.compare_all([])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'single.ram'
            path.write_bytes(bytes(analyze.RAM_SIZE))
            with self.assertRaisesRegex(ValueError, 'at least two'):
                analyze.compare_all([path])

    def test_reject_incomplete_ram(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'short.ram'
            path.write_bytes(b'\0'*128)
            with self.assertRaises(ValueError):
                analyze.compare_all([path])

    def test_normal_process_exit_is_not_gameplay_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'run.json').write_text('{"exit_code":0,"semantic_pass":false}')
            output = root/'result.json'
            with patch('sys.argv', ['analyze.py', str(root), '--output', str(output)]):
                with self.assertRaisesRegex(ValueError, 'gameplay verification'):
                    analyze.main()
            self.assertFalse(output.exists())

    def test_signed_fixed_point(self):
        result = analyze.summarize([{'phase':'rest', 'mode':3,
            'x':-2, 'y':30000, 'z':-32000,
            'fixedX':-2*65536, 'fixedY':30000*65536, 'fixedZ':-32000*65536}])
        self.assertEqual(result['rest']['max_actor_physics_difference_xyz'], [0,0,0])
        self.assertEqual(result['rest']['fields']['x']['values'], [-2])


if __name__ == '__main__':
    unittest.main()
