"""Maintainer-only smoke of an actual frozen archive; never starts an emulator."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile


def unpack(archive, destination):
    destination=Path(destination).resolve()
    with zipfile.ZipFile(archive)as z:
        for item in z.infolist():
            name=PurePosixPath(item.filename)
            if name.is_absolute()or'..'in name.parts or not name.parts or name.parts[0]!='MediEvil-Minimap' or any(':'in part for part in name.parts):
                raise ValueError('Unexpected archive path')
            target=destination.joinpath(*name.parts)
            if not target.resolve().is_relative_to(destination):raise ValueError('Archive path escapes extraction directory')
            target.parent.mkdir(parents=True,exist_ok=True)
            mode=item.external_attr>>16
            if stat.S_ISLNK(mode):
                link=z.read(item).decode('utf-8')
                if Path(link).is_absolute()or not(target.parent/link).resolve().is_relative_to(destination):raise ValueError('Unsafe archive symlink')
                target.symlink_to(link)
            elif item.is_dir():target.mkdir(exist_ok=True)
            else:
                with z.open(item)as source,target.open('xb')as output:shutil.copyfileobj(source,output)
                if mode&0o777:target.chmod(mode&0o777)
    return destination/'MediEvil-Minimap'


def smoke(archive):
    with tempfile.TemporaryDirectory(prefix='LiveMap smoke café ')as temp:
        root=unpack(archive,Path(temp)/'unpacked')
        executable=root/('MediEvilMinimap.exe'if sys.platform=='win32'else'MediEvilMinimap')
        if not executable.is_file():raise ValueError('Archive has no native executable; source ZIP is not a standalone build')
        # Remove source fallback/resources at the archive root. The executable
        # must use its bundled interpreter and _internal resources instead.
        for file in root.glob('*.py'):file.unlink()
        shutil.rmtree(root/'web')
        (root/'fence_materials.json').unlink()
        env=os.environ.copy()
        for key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV'):env.pop(key,None)
        env['PYTHONNOUSERSITE']='1'
        env['PATH']=os.pathsep.join([str(Path(env.get('SystemRoot','C:/Windows'))/'System32'),env.get('SystemRoot','C:/Windows')])if sys.platform=='win32'else'/usr/bin:/bin'
        child=subprocess.Popen([str(executable),'--no-open','--port','0','--data-dir',str(Path(temp)/'empty cache')],cwd=root,
            env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        lines=queue.Queue();output=[]
        def consume():
            for line in child.stdout:lines.put(line)
        reader=threading.Thread(target=consume,daemon=True);reader.start()
        try:
            deadline=time.monotonic()+30;url=None
            while time.monotonic()<deadline:
                try:line=lines.get(timeout=.2)
                except queue.Empty:
                    if child.poll()is not None:break
                    continue
                output.append(line)
                match=re.search(r'http://127\.0\.0\.1:\d+',line)
                if match:url=match[0];break
            if not url:raise RuntimeError('Frozen app did not start: '+''.join(output)[-3000:])
            with urllib.request.urlopen(url,timeout=5)as response:
                if b'Build your maps once'not in response.read():raise RuntimeError('Setup resources unavailable')
            with urllib.request.urlopen(url+'/api/setup',timeout=5)as response:state=json.load(response)
            if state['ready']or state['busy']:raise RuntimeError('Empty-cache setup was not isolated')
            with urllib.request.urlopen(url+'/dan.png',timeout=5)as response:
                if response.headers.get_content_type()!='image/svg+xml' or b'<svg'not in response.read():raise RuntimeError('Bundled neutral marker unavailable')
            return {'standalone_startup':True,'bundled_setup_and_marker':True,'root_python_source_removed':True,
                'no_emulator_started':True,'duckstation_gameplay_verified':False,'platform':sys.platform}
        finally:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
            reader.join(timeout=2)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path);args=parser.parse_args()
    print(json.dumps(smoke(args.archive),indent=2))
