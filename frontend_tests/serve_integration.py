"""Frontend integration server: real API/data, isolated disposable SQLite.
Run from the project root: python frontend_tests/serve_integration.py
Never uses or modifies the application's runtime database.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_server
with tempfile.TemporaryDirectory(prefix='relai-frontend-', dir='/home/remi/.hermes/cache/scratch') as scratch:
    server = create_server(port=8128, db_path=Path(scratch)/'integration.sqlite3')
    print('Frontend isolated integration server http://127.0.0.1:8128', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
