"""Build a sanitized, server-free GitHub Pages artifact (never copy runtime)."""
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.generate_demo import generate_teachers

ROOT = Path(__file__).resolve().parents[1]

def build(output):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents and output.name not in ('pages', 'pages-site'):
        raise ValueError('Use a dedicated pages output directory.')
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'static', output, dirs_exist_ok=True)
    html = (output / 'index.html').read_text()
    html = html.replace('<head>', '<head><meta name="relai-mode" content="static">').replace('/static/', './').replace('href="/"', 'href="./"')
    (output / 'index.html').write_text(html)
    (output / '.nojekyll').write_text('')
    data = output / 'data'
    data.mkdir(exist_ok=True)
    for name in ('schools.json', 'calendar.json', 'SOURCES.md'):
        shutil.copy2(ROOT / 'data' / name, data / name)
    schools = json.loads((data / 'schools.json').read_text())['schools']
    teachers = generate_teachers(schools, today=dt.date.today())
    (data / 'teachers.json').write_text(json.dumps({'demo': True, 'teachers': teachers}, ensure_ascii=False, allow_nan=False))
    files = [p for p in output.rglob('*') if p.is_file()]
    assert not any(p.suffix in ('.sqlite3', '.db', '.key', '.pem') or p.name.startswith('.env') for p in files)
    print(json.dumps({'output': str(output), 'schools': len(schools), 'teachers': len(teachers), 'files': len(files)}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/pages')
    build(parser.parse_args().output)
