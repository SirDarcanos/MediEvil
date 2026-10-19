"""Layout and Git-ignore contracts; no game or emulator is launched."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tools import run

ROOT = Path(__file__).resolve().parents[1]


class LayoutTests(unittest.TestCase):
    def test_default_probe_is_bundled_and_independent_of_working_directory(self):
        self.assertEqual(run.DEFAULT_PROBE, ROOT / 'probes' / 'probe.lua')
        self.assertTrue(run.DEFAULT_PROBE.is_file())
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'tools' / 'run.py'), '--help'],
                cwd=directory, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--probe', result.stdout)


@unittest.skipUnless(shutil.which('git'), 'Git is required to exercise ignore rules')
class IgnoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(['git', 'init', '--quiet', '--initial-branch=ignore-test'],
                       cwd=self.root, check=True, capture_output=True, timeout=10)
        (self.root / '.gitignore').write_bytes((ROOT / '.gitignore').read_bytes())

    def ignored(self, names):
        result = subprocess.run(
            ['git', '-c', 'core.excludesFile=/dev/null', 'check-ignore', '--no-index', '--stdin'],
            cwd=self.root, input='\n'.join(names) + '\n', text=True,
            capture_output=True, timeout=10)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return set(result.stdout.splitlines())

    def test_generated_and_private_artifacts_are_ignored(self):
        names = ['tools/__pycache__/run.cpython-314.pyc', 'ghidra/AuditMemory.class',
                 'runs/example/run.json', 'outputs/frame.png', 'scratch/log.txt',
                 'inputs/MEDIEVIL.EXE', 'capture.ram', 'capture.pixels',
                 'end.state.gz', 'card1.mcd', 'local.gpr', 'local.rep/project.prp',
                 'ReduxAudit.app/Contents/MacOS/ReduxAudit']
        self.assertEqual(self.ignored(names), set(names))

    def test_source_evidence_notes_and_diagrams_remain_visible(self):
        names = ['tools/run.py', 'tests/test_run.py', 'probes/army.lua',
                 'ghidra/LoadOverlayAudit.java', 'evidence/verified-runs.json',
                 'evidence/inventory-table.json', 'notes/physics.md',
                 'notes/diagram.png', 'README.md']
        self.assertEqual(self.ignored(names), set())


if __name__ == '__main__':
    unittest.main()
