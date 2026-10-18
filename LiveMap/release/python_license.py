"""Build-only: obtain the license for the exact CPython interpreter being bundled."""
import argparse
from pathlib import Path
import platform
import re
import urllib.request

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    version=platform.python_version()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):parser.error('Use a stable CPython build')
    url=f'https://raw.githubusercontent.com/python/cpython/v{version}/LICENSE'
    with urllib.request.urlopen(url,timeout=30)as response:data=response.read(128*1024)
    if b'PYTHON SOFTWARE FOUNDATION'not in data:raise ValueError('Unexpected CPython license response')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb')as output:output.write(data)
    print(f'CPython {version} license saved from the matching official release tag.')
