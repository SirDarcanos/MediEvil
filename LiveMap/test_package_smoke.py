import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec=importlib.util.spec_from_file_location('package_smoke',Path(__file__).with_name('release')/'smoke_package.py')
smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)

class PackageSmokeTests(unittest.TestCase):
    def test_unpacks_regular_files_in_owned_directory(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);archive=root/'safe.zip'
            with zipfile.ZipFile(archive,'w')as z:z.writestr('MediEvil-Minimap/README.md','own fixture')
            destination=smoke.unpack(archive,root/'output')
            self.assertEqual((destination/'README.md').read_text(),'own fixture')
    def test_rejects_archive_traversal(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);archive=root/'bad.zip'
            with zipfile.ZipFile(archive,'w')as z:z.writestr('MediEvil-Minimap/../../outside','bad')
            with self.assertRaises(ValueError):smoke.unpack(archive,root/'output')
            self.assertFalse((root/'outside').exists())
    def test_rejects_external_symlink_before_creating_it(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);archive=root/'bad-link.zip'
            info=zipfile.ZipInfo('MediEvil-Minimap/link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
            with zipfile.ZipFile(archive,'w')as z:z.writestr(info,'../../outside')
            with self.assertRaises(ValueError):smoke.unpack(archive,root/'output')
    def test_never_calls_python_as_fallback_for_source_archive(self):
        with tempfile.TemporaryDirectory()as tmp:
            archive=Path(tmp)/'source.zip'
            with zipfile.ZipFile(archive,'w')as z:z.writestr('MediEvil-Minimap/runner.py','print("not executed")')
            with patch.object(smoke.subprocess,'Popen')as child:
                with self.assertRaisesRegex(ValueError,'no native executable'):smoke.smoke(archive)
                child.assert_not_called()

if __name__=='__main__':unittest.main()
