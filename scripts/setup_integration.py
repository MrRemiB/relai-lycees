"""Generate an integration credential without displaying it or storing cleartext server-side."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets


def setup(server_file,client_file,identifier,scopes):
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}',identifier) or not scopes or len(set(scopes))!=len(scopes) or set(scopes)-{'read','config','import'}: raise ValueError('ID et scopes explicites read/config/import requis.')
    server_file=Path(server_file); client_file=Path(client_file)
    if server_file.resolve()==client_file.resolve(): raise ValueError('Fichiers distincts requis.')
    if server_file.exists() or client_file.exists(): raise FileExistsError('Refus d’écraser une habilitation existante.')
    token=secrets.token_urlsafe(48)
    server_file.parent.mkdir(parents=True,exist_ok=True); client_file.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive 0600 writes; no credential value in stdout or argv.
    made=[]
    try:
        for path,data in [(server_file,json.dumps([dict(id=identifier,token_hash=hashlib.sha256(token.encode()).hexdigest(),scopes=scopes)])+'\n'),(client_file,'RELAI_TOKEN='+token+'\n')]:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); made.append(path)
            with os.fdopen(fd,'w') as f: f.write(data)
    except Exception:
        for path in made: path.unlink(missing_ok=True)
        raise
    print('Credential generated: server hash file and client environment file mode 0600. No secret displayed.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-file',required=True); parser.add_argument('--client-file',required=True); parser.add_argument('--id',required=True); parser.add_argument('--scopes',nargs='+',required=True)
    args=parser.parse_args(); setup(args.server_file,args.client_file,args.id,args.scopes)
