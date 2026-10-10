"""Consistent SQLite online backup; destination must not exist."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3

def backup(source,target):
    source=Path(source).resolve(); target=Path(target).resolve()
    if not source.is_file(): raise ValueError('Base source introuvable.')
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=15)) as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst,pages=256,sleep=.1)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or dst.execute('PRAGMA foreign_key_check').fetchall(): raise ValueError('Sauvegarde invalide.')
        print('Sauvegarde cohérente SQLite créée, intégrité et clés étrangères vérifiées.')
    except Exception:
        target.unlink(missing_ok=True); raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('source'); parser.add_argument('target'); args=parser.parse_args(); backup(args.source,args.target)
