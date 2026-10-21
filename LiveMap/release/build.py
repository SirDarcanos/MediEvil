#!/usr/bin/env python3
"""Build a minimap-only ZIP from an explicit allowlist; no game assets or caches.

Default: portable source ZIP. --standalone: freeze on the target OS with an
already-installed PyInstaller (never installs dependencies or cross-compiles).
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=('runner.py','app.py','feed.py','local_http.py','ram.py','emulator_memory.py','gdb_reader.py','disc_import.py',
         'extract_maps.py','binary.py','vlo.py','appearance.py','textures.py','objects.py','triggers.py',
         'scripted_exits.py','edge_on.py','fence_materials.json')
WEB=('index.html','app.js','terrain.js','raster.js','movement.js','style.css','setup.html','setup.js','setup.css','marker.svg')
LAUNCHERS=('Open Minimap.cmd','Open Minimap.command','open-minimap.sh')


def assemble(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    (destination/'web').mkdir()
    for name in RUNTIME:shutil.copy2(ROOT/name,destination/name)
    for name in WEB:shutil.copy2(ROOT/'web'/name,destination/'web'/name)
    for name in LAUNCHERS:
        target=destination/name;shutil.copy2(ROOT/'release/launchers'/name,target)
        if name.endswith(('.command','.sh')):target.chmod(0o755)
    shutil.copy2(ROOT/'RUNNERS.md',destination/'README.md')
    shutil.copy2(ROOT/'THIRD_PARTY.md',destination/'THIRD_PARTY.md')
    shutil.copy2(ROOT/'LICENSE.txt',destination/'LICENSE.txt')
    return destination


def build(output,standalone=False,python_license=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if standalone and importlib.util.find_spec('PyInstaller')is None:
        raise ValueError('Standalone builds require PyInstaller on the target OS. No dependencies were installed. See release/BUILD.md.')
    if standalone:
        candidates=[Path(python_license)]if python_license else [Path(sys.base_prefix)/'LICENSE.txt',Path(sys.base_prefix)/'LICENSE']
        python_license=next((p for p in candidates if p.is_file()),None)
        if python_license is None:
            raise ValueError('Supply the bundled interpreter license with --python-license PATH.')
        distribution=importlib.metadata.distribution('pyinstaller')
        installer_license=next((Path(distribution.locate_file(p))for p in distribution.files or []
            if p.name in ('COPYING.txt','COPYING','COPYING.rst')and Path(distribution.locate_file(p)).is_file()),None)
        if installer_license is None:
            raise ValueError('PyInstaller license was not found in the build environment; do not publish this bundle.')
    with tempfile.TemporaryDirectory(prefix='medievil-release-')as scratch:
        temp=Path(scratch);folder=assemble(temp/'MediEvil-Minimap')
        suffix='source'
        if standalone:
            shutil.copy2(python_license,folder/'PYTHON-LICENSE.txt')
            shutil.copy2(installer_license,folder/'PYINSTALLER-LICENSE.txt')
            subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
                '--name','MediEvilMinimap','--distpath',str(temp/'native'),'--workpath',str(temp/'work'),
                '--specpath',str(temp/'spec'),'--add-data',str(folder/'web')+os.pathsep+'web',
                '--add-data',str(folder/'fence_materials.json')+os.pathsep+'.',
                str(folder/'runner.py')],cwd=folder,check=True)
            native=temp/'native/MediEvilMinimap'
            for item in native.iterdir():
                target=folder/item.name
                if item.is_dir():shutil.copytree(item,target,symlinks=True)
                else:shutil.copy2(item,target)
            suffix=platform.system().lower()+'-'+platform.machine().lower()
        name=f'MediEvil-Minimap-v1-{suffix}.zip'
        archive=output/name
        if archive.exists():raise ValueError('Output already exists; choose a new output directory to preserve prior builds.')
        hashes={str(f.relative_to(folder)):hashlib.sha256(f.read_bytes()).hexdigest()
                for f in sorted(folder.rglob('*'))if f.is_file()}
        (folder/'CONTENTS.sha256').write_text(''.join(f'{digest}  {name}\n'for name,digest in hashes.items()),encoding='utf-8')
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED)as z:
            for path in sorted(folder.rglob('*')):
                relative=(Path('MediEvil-Minimap')/path.relative_to(folder)).as_posix()
                if path.is_symlink():
                    if not path.resolve().is_relative_to(folder.resolve()):
                        raise ValueError('Standalone bundle contains an external symlink.')
                    info=zipfile.ZipInfo(relative);info.create_system=3
                    info.external_attr=(stat.S_IFLNK|0o777)<<16
                    z.writestr(info,os.readlink(path))
                elif path.is_file():
                    info=zipfile.ZipInfo.from_file(path,relative)
                    if path.name in ('Open Minimap.command','open-minimap.sh'):
                        # Windows chmod/stat do not preserve POSIX execute bits.
                        # The portable source ZIP still needs runnable Unix launchers.
                        info.create_system=3
                        info.external_attr=(stat.S_IFREG|0o755)<<16
                    info.compress_type=zipfile.ZIP_DEFLATED
                    with path.open('rb')as source,z.open(info,'w')as target:
                        shutil.copyfileobj(source,target)
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        (output/(name+'.sha256')).write_text(digest+'  '+name+'\n',encoding='utf-8')
        print(json.dumps({'archive':str(archive.resolve()),'sha256':digest,'kind':suffix,'files':len(hashes)+1},indent=2))
        return archive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--standalone',action='store_true')
    parser.add_argument('--python-license',type=Path,help='License for the bundled CPython version; standalone builds only')
    args=parser.parse_args()
    try:build(args.output,args.standalone,args.python_license)
    except (ValueError,OSError,subprocess.CalledProcessError)as error:parser.exit(1,str(error)+'\n')
if __name__=='__main__':main()
