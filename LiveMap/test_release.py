import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import stat
import subprocess
import sys
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
    def test_packaged_source_entry_points_import_without_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = build.assemble(Path(tmp) / 'source package')
            for entry_point in ('runner.py', 'app.py'):
                with self.subTest(entry_point=entry_point):
                    result = subprocess.run(
                        [sys.executable, '-E', str(package / entry_point), '--help'],
                        cwd=tmp, capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('--gdb-port', result.stdout)
            page = (package / 'web/index.html').read_text()
            for script in ('terrain.js', 'raster.js', 'movement.js', 'app.js'):
                self.assertIn(f'src="/{script}"', page)
                self.assertEqual((package / 'web' / script).read_bytes(),
                                 (build.ROOT / 'web' / script).read_bytes())

    def test_windows_zip_metadata_still_marks_unix_launchers_executable(self):
        original=zipfile.ZipInfo.from_file
        def windows_info(filename,arcname=None,*,strict_timestamps=True):
            info=original(filename,arcname,strict_timestamps=strict_timestamps)
            info.create_system=0
            info.external_attr=(stat.S_IFREG|0o666)<<16
            return info
        with tempfile.TemporaryDirectory()as tmp:
            with patch.object(zipfile.ZipInfo,'from_file',side_effect=windows_info):archive=build.build(tmp)
            with zipfile.ZipFile(archive)as z:
                for name in ('Open Minimap.command','open-minimap.sh'):
                    info=z.getinfo('MediEvil-Minimap/'+name)
                    self.assertEqual(info.create_system,3)
                    self.assertEqual((info.external_attr>>16)&0o777,0o755)

    def test_standalone_missing_build_dependency_fails_without_install(self):
        if importlib.util.find_spec('PyInstaller')is not None:self.skipTest('Builder installed on this environment')
        with tempfile.TemporaryDirectory()as tmp:
            with self.assertRaisesRegex(ValueError,'No dependencies were installed'):build.build(tmp,True)
            self.assertEqual(list(Path(tmp).iterdir()),[])

if __name__=='__main__':unittest.main()
