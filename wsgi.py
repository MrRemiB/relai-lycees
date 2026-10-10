"""Gunicorn entrypoint: load only allowlisted environment keys, never execute shell."""
import os
from pathlib import Path
import shlex
from production import from_environment

ENV_KEYS={'RELAI_PASSWORD_HASH','RELAI_SESSION_SECRET','RELAI_ORIGIN','RELAI_DB','RELAI_COOKIE_SECURE','RELAI_INTEGRATIONS_FILE','RELAI_INTEGRATIONS_JSON'}
def load_env(path):
    path=Path(path)
    if not path.exists(): return
    if path.stat().st_mode & 0o077: raise ValueError('Fichier de secrets : permissions 0600 requises.')
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'): continue
        key,sep,value=line.partition('=')
        if not sep or key not in ENV_KEYS: raise ValueError('Clé environnement non autorisée.')
        parts=shlex.split(value,comments=False)
        if len(parts)!=1: raise ValueError('Valeur environnement invalide.')
        os.environ.setdefault(key,parts[0])

load_env(os.environ.get('RELAI_ENV_FILE',str(Path(__file__).parent/'.env')))
application=from_environment()
