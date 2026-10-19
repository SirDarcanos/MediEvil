import tempfile
import unittest
from pathlib import Path
from tools import run


class IsolationTests(unittest.TestCase):
    def test_private_copy_renames_only_the_copy_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'original/PCSX-Redux.app'
            source = app / 'Contents/MacOS/PCSX-Redux'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'unchanged emulator fixture')
            resource = app / 'Contents/Resources/example'
            resource.parent.mkdir(parents=True)
            resource.write_bytes(b'unchanged resource fixture')
            output = root / 'our-run'
            output.mkdir()
            private = run.private_emulator(source, output)
            self.assertEqual(private.name, 'ReduxAudit')
            self.assertEqual(private.read_bytes(), source.read_bytes())
            self.assertTrue(source.is_file())
            self.assertFalse((private.parent / 'PCSX-Redux').exists())
            self.assertEqual((output / 'ReduxAudit.app/Contents/Resources/example').read_bytes(),
                             resource.read_bytes())
            with self.assertRaises(FileExistsError):
                run.private_emulator(source, output)
            self.assertEqual(source.read_bytes(), b'unchanged emulator fixture')


if __name__ == '__main__':
    unittest.main()
