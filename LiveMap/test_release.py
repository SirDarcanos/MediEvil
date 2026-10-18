import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

path=Path(__file__).with_name('release')/'build.py'
spec=importlib.util.spec_from_file_location('release_build',path)
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

class ReleaseTests(unittest.TestCase):
    def test_source_archive_is_exact_allowlist_without_game_or_research_assets(self):
        with tempfile.TemporaryDirectory()as tmp:
            archive=build.build(Path(tmp)/'output')
            with zipfile.ZipFile(archive)as z:
                names={n.removeprefix('MediEvil-Minimap/')for n in z.namelist()}
                expected=set(build.RUNTIME)|{'web/'+n for n in build.WEB}|set(build.LAUNCHERS)|{'README.md','THIRD_PARTY.md','LICENSE.txt','CONTENTS.sha256'}
                self.assertEqual(names,expected)
                self.assertFalse(any(n.endswith(('.png','.bin','.sav','.cue','.state'))for n in names))
                self.assertIn(b'first-run',z.read('MediEvil-Minimap/runner.py'))
                self.assertEqual((z.getinfo('MediEvil-Minimap/Open Minimap.command').external_attr>>16)&0o777,0o755)
            with self.assertRaises(ValueError):build.build(Path(tmp)/'output')
    def test_standalone_missing_build_dependency_fails_without_install(self):
        if importlib.util.find_spec('PyInstaller')is not None:self.skipTest('Builder installed on this environment')
        with tempfile.TemporaryDirectory()as tmp:
            with self.assertRaisesRegex(ValueError,'No dependencies were installed'):build.build(tmp,True)
            self.assertEqual(list(Path(tmp).iterdir()),[])

if __name__=='__main__':unittest.main()
