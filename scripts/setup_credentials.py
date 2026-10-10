"""Create a new 0600 environment file; passwords only from masked TTY prompts."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from production import hash_password, validate_config

def setup(path,origin,db):
    path=Path(path)
    if path.exists(): raise FileExistsError('Refus d’écraser des secrets existants. Créer un nouveau fichier pour rotation.')
    if not sys.stdin.isatty(): raise ValueError('Terminal interactif requis pour saisie masquée. Ne pas passer le mot de passe en argument ou variable.')
    password=getpass.getpass('Mot de passe coordinateur (16 caractères minimum) : ')
    if password!=getpass.getpass('Confirmer (masqué) : '): raise ValueError('Confirmation différente.')
    config=validate_config(dict(password_hash=hash_password(password),session_secret=secrets.token_urlsafe(48),origin=origin,secure=True))
    env=dict(RELAI_PASSWORD_HASH=config['password_hash'],RELAI_SESSION_SECRET=config['session_secret'],RELAI_ORIGIN=origin,RELAI_DB=str(Path(db).resolve()),RELAI_COOKIE_SECURE='true')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as file:
        for key,value in env.items(): file.write(key+'='+json.dumps(value,ensure_ascii=False)+'\n')
    print('Fichier 0600 créé. Aucun secret affiché. Redémarrer le service après installation.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',default='.env'); parser.add_argument('--origin',required=True); parser.add_argument('--db',default='runtime/pilot.sqlite3'); args=parser.parse_args()
    setup(args.output,args.origin,args.db)
