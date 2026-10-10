#!/usr/bin/env python3
"""Package a portable anonymous demonstration, never the runtime database."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def build():
    files=[]
    for name in ['app.py','matching.py','routing.py','start.sh','README.md','QA.md','PRODUCT.md','CONTRACT.md','ROUTING_CONTRACT.md','DESIGN.md','.impeccable/design.json','.gitignore','.github/workflows/tests.yml']:
        path=ROOT/name
        if not path.is_file():
            raise RuntimeError(f'Missing deliverable {name}')
        files.append(path)
    for folder in ['static','data','scripts','tests','frontend_tests']:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files=sorted(set(files))
    forbidden=('runtime','dist','.env','node_modules','.git')
    for path in files:
        relative=path.relative_to(ROOT)
        if any(part in forbidden or part.startswith('.env') for part in relative.parts) or path.suffix in ['.sqlite3','.sqlite','.db','.pem','.key']:
            raise RuntimeError(f'Forbidden archive path {relative}')
    target=ROOT/'dist'/'relai-lycees-demo.zip'
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path,Path('relai-lycees')/path.relative_to(ROOT))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        assert 'relai-lycees/data/schools.json' in archive.namelist()
        assert 'relai-lycees/static/vendor/leaflet/leaflet.js' in archive.namelist()
    print(json.dumps({'path':str(target),'files':len(files),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'runtime_included':False},indent=2))

if __name__=='__main__':
    build()
