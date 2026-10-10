"""Authenticated coordinator pilot WSGI adapter, reusing Store.dispatch unchanged."""
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote
from app import APIError, ROOT, Store, decode_json
from batches import BatchService

MAX_BODY=3_000_000
ITERATIONS=600000
COOKIE='relai_session'

def hash_password(password):
    if not isinstance(password,str) or len(password)<16 or len(password)>1024: raise ValueError('Mot de passe de 16 à 1024 caractères requis.')
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),ITERATIONS).hex()
    return f'pbkdf2_sha256${ITERATIONS}${salt}${digest}'
def validate_config(config):
    config=dict(config)
    if not re.fullmatch(r'pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}',config.get('password_hash','')): raise ValueError('RELAI_PASSWORD_HASH valide requis ; scripts/setup_credentials.py')
    if len(config.get('session_secret',''))<32: raise ValueError('RELAI_SESSION_SECRET aléatoire (32 caractères minimum) requis.')
    origin=config.get('origin',''); parsed=urlsplit(origin)
    secure=config.get('secure',True)
    if not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.scheme not in ('https','http'): raise ValueError('RELAI_ORIGIN doit être une origine exacte sans chemin.')
    if parsed.scheme!='https' and (secure or parsed.hostname not in ('127.0.0.1','localhost')): raise ValueError('HTTPS requis sauf test HTTP loopback explicitement non sécurisé.')
    config['secure']=secure
    integrations=config.get('integrations',[])
    if not isinstance(integrations,list) or len(integrations)>50: raise ValueError('Maximum 50 intégrations.')
    seen=set()
    for item in integrations:
        if not isinstance(item,dict) or set(item)!={'id','token_hash','scopes'} or not isinstance(item['id'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}',item['id']) or item['id'] in seen: raise ValueError('Intégration stricte ID unique requis.')
        seen.add(item['id'])
        if not isinstance(item['token_hash'],str) or not re.fullmatch('[0-9a-f]{64}',item['token_hash']): raise ValueError('SHA256 token requis.')
        if not isinstance(item['scopes'],list) or not item['scopes'] or len(set(item['scopes']))!=len(item['scopes']) or set(item['scopes'])-{'read','config','import'}: raise ValueError('Scopes read/config/import explicites requis.')
    config['integrations']=integrations
    return config

def from_environment():
    if os.environ.get('RELAI_COOKIE_SECURE','true') not in ('true','false'): raise ValueError('RELAI_COOKIE_SECURE true ou false requis.')
    config=validate_config(dict(password_hash=os.environ.get('RELAI_PASSWORD_HASH',''),session_secret=os.environ.get('RELAI_SESSION_SECRET',''),origin=os.environ.get('RELAI_ORIGIN',''),secure=os.environ.get('RELAI_COOKIE_SECURE','true')=='true'))
    token_file=os.environ.get('RELAI_INTEGRATIONS_FILE')
    if token_file:
        token_path=Path(token_file)
        if token_path.stat().st_mode & 0o077: raise ValueError('Fichier intégrations mode 0600 requis.')
        config['integrations']=decode_json(token_path.read_bytes())
    elif os.environ.get('RELAI_INTEGRATIONS_JSON'): config['integrations']=decode_json(os.environ['RELAI_INTEGRATIONS_JSON'])
    config=validate_config(config)
    dbpath=Path(os.environ.get('RELAI_DB',str(ROOT/'runtime/pilot.sqlite3'))).resolve()
    # A second process/worker is unsafe: fail start instead of duplicating jobs.
    import fcntl
    dbpath.parent.mkdir(parents=True,exist_ok=True)
    lock=open(str(dbpath)+'.worker.lock','a')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: lock.close(); raise ValueError('Un seul processus Gunicorn autorisé pour cette base.') from None
    schools=decode_json((ROOT/'data/schools.json').read_bytes()); calendar=decode_json((ROOT/'data/calendar.json').read_bytes())
    app=create_app(Store(dbpath,schools,None,calendar),config); app.process_lock=lock
    return app

LOGIN='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Relai · connexion pilote</title><h1>Relai Lycées · pilote coordinateur</h1><p>Compte coordinateur partagé, sans SSO. Profils fictifs exclusivement ; pas un service RH national homologué.</p><form method="post" action="/login"><label>Mot de passe coordinateur <input name="password" type="password" autocomplete="current-password" required maxlength="1024"></label><button>Se connecter</button></form></html>'''

class PilotApplication:
    def __init__(self,store,config):
        self.store=store; self.config=validate_config(config); self.batches=BatchService(store)
        with store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS pilot_sessions(id TEXT PRIMARY KEY,csrf TEXT NOT NULL,expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS pilot_login_limits(ip TEXT PRIMARY KEY,attempts INTEGER NOT NULL,until REAL NOT NULL);''')
    def signed(self,identifier):
        return identifier+'.'+hmac.new(self.config['session_secret'].encode(),identifier.encode(),hashlib.sha256).hexdigest()
    def session(self,env):
        try:
            cookie=SimpleCookie(); cookie.load(env.get('HTTP_COOKIE','')); value=cookie[COOKIE].value
            identifier=value.split('.')[0]
            if len(identifier)!=64 or not hmac.compare_digest(value,self.signed(identifier)): return None
        except (KeyError,ValueError): return None
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM pilot_sessions WHERE id=? AND expires>?',(identifier,time.time())).fetchone()
            return dict(row) if row else None
    def cookie(self,value,age=28800):
        return f'{COOKIE}={value}; Path=/; Max-Age={age}; HttpOnly; SameSite=Strict'+('; Secure' if self.config['secure'] else '')
    def origin(self,env):
        if env.get('HTTP_ORIGIN')!=self.config['origin'] or env.get('HTTP_SEC_FETCH_SITE') in ('cross-site','same-site'): raise APIError(403,'Origine exacte requise.')
    def payload(self,env,form=False):
        if env.get('HTTP_TRANSFER_ENCODING'): raise APIError(400,'Transfer-Encoding interdit.')
        length=env.get('CONTENT_LENGTH','')
        if not re.fullmatch('[0-9]+',length): raise APIError(400,'Content-Length requis.')
        if int(length)>MAX_BODY: raise APIError(413,'Corps limité à 3 Mo.')
        raw=env['wsgi.input'].read(int(length))
        if len(raw)!=int(length): raise ValueError('Corps incomplet')
        content=env.get('CONTENT_TYPE','').split(';')[0].strip().lower()
        if form and content=='application/x-www-form-urlencoded':
            parsed=parse_qs(raw.decode(),strict_parsing=True)
            if set(parsed)!={'password'} or len(parsed['password'])!=1: raise ValueError('Formulaire invalide')
            return {'password':parsed['password'][0]},True
        if content!='application/json': raise APIError(415,'application/json requis.')
        p=decode_json(raw)
        if not isinstance(p,dict): raise ValueError('Objet JSON requis')
        return p,False
    def login(self,env,p):
        if set(p)!={'password'} or not isinstance(p['password'],str) or len(p['password'])>1024: raise ValueError('Identifiants invalides')
        ip=env.get('REMOTE_ADDR','unknown') # Never trust user-controlled forwarding headers.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); now=time.time()
            db.execute('DELETE FROM pilot_login_limits WHERE until<?',(now,))
            row=db.execute('SELECT attempts FROM pilot_login_limits WHERE ip=?',(ip,)).fetchone()
            if row and row['attempts']>=10: raise APIError(429,'Trop de tentatives ; attendre 15 minutes.')
            db.execute('INSERT INTO pilot_login_limits VALUES(?,1,?) ON CONFLICT(ip) DO UPDATE SET attempts=attempts+1',(ip,now+900))
        _,iterations,salt,digest=self.config['password_hash'].split('$')
        calculated=hashlib.pbkdf2_hmac('sha256',p['password'].encode(),bytes.fromhex(salt),int(iterations)).hex()
        if not hmac.compare_digest(calculated,digest): raise APIError(401,'Connexion refusée.')
        identifier=secrets.token_hex(32); csrf=secrets.token_hex(32)
        with self.store.connect() as db:
            db.execute('DELETE FROM pilot_sessions WHERE expires<=?',(time.time(),))
            previous=self.session(env)
            if previous: db.execute('DELETE FROM pilot_sessions WHERE id=?',(previous['id'],))
            db.execute('INSERT INTO pilot_sessions VALUES(?,?,?)',(identifier,csrf,time.time()+28800))
        return identifier,csrf
    def integration(self,env,method,path):
        # No fallback to a session, cookie mixing, query token or browser CSRF bypass.
        if env.get('HTTP_COOKIE') or env.get('QUERY_STRING') and path!='/api/v1/events': raise APIError(403,'Bearer seul, sans cookie ni query secret.')
        value=env.get('HTTP_AUTHORIZATION','')
        match=re.fullmatch(r'Bearer ([A-Za-z0-9_-]{32,256})',value)
        digest=hashlib.sha256((match[1] if match else '').encode()).hexdigest(); found=None
        for item in self.config['integrations']:
            equal=hmac.compare_digest(digest,item['token_hash'])
            if equal and match: found=item
        if found is None: raise APIError(401,'Jeton intégration refusé.')
        scope='read' if method=='GET' and (path=='/api/v1/config' or path=='/api/v1/events' or path.startswith('/api/v1/reference/')) else 'config' if method=='PUT' and path=='/api/v1/config' else 'import' if method=='POST' and path in ('/api/v1/imports/validate','/api/v1/imports/commit') else None
        if scope is None or scope not in found['scopes']: raise APIError(403,'Route ou scope intégration interdit.')
        return 'integration:'+found['id']

    def __call__(self,env,start_response):
        extra=[]; content='application/json; charset=utf-8'
        try:
            method=env.get('REQUEST_METHOD'); path=unquote(env.get('PATH_INFO','/'))
            if path=='/health' and method=='GET': status,body=200,{'status':'ok'}
            elif path=='/login' and method=='GET': status,body,content=200,LOGIN,'text/html; charset=utf-8'
            elif path=='/login' and method=='POST':
                self.origin(env); p,form=self.payload(env,form=True); identifier,csrf=self.login(env,p)
                extra.append(('Set-Cookie',self.cookie(self.signed(identifier))))
                status,body=200,dict(csrf_token=csrf,role='coordinator')
                if form: status=303; extra.append(('Location','/'))
            else:
                bearer=bool(env.get('HTTP_AUTHORIZATION'))
                actor=self.integration(env,method,path) if bearer else 'coordinator'
                session=None if bearer else self.session(env)
                if not bearer and not session: raise APIError(401,'Connexion requise : /login')
                if method in ('POST','PUT'):
                    if not bearer:
                        self.origin(env)
                        if not hmac.compare_digest(env.get('HTTP_X_CSRF_TOKEN',''),session['csrf']): raise APIError(403,'Jeton CSRF requis.')
                    p,_=self.payload(env)
                else: p=None
                if path=='/logout' and method=='POST':
                    if p: raise ValueError('Objet vide requis')
                    with self.store.connect() as db: db.execute('DELETE FROM pilot_sessions WHERE id=?',(session['id'],))
                    extra.append(('Set-Cookie',self.cookie('',0))); status,body=200,{'logged_out':True}
                elif path=='/api/batches' and method=='POST': status,body=201,{'job':self.batches.create(p)}
                elif path=='/api/batches' and method=='GET': status,body=200,{'jobs':self.batches.list()}
                elif (found:=re.fullmatch('/api/batches/([0-9a-f]{32})(?:/(run|cancel))?',path)):
                    j,action=found.groups()
                    if method=='GET' and action is None: status,body=200,{'job':self.batches.get(j)}
                    elif method=='POST' and action in ('run','cancel'):
                        if p: raise ValueError('Objet vide requis')
                        status,body=(202 if action=='run' else 200),{'job':getattr(self.batches,action)(j)}
                    else: raise APIError(404,'Ressource introuvable.')
                elif path.startswith('/api/'):
                    status,body=self.store.dispatch(method,path,p,actor=actor,query=env.get('QUERY_STRING',''))
                    if path=='/api/bootstrap': body.update(csrf_token=session['csrf'],auth=dict(role='coordinator',sso=False,pilot=True))
                elif method=='GET':
                    relative='index.html' if path=='/' else path[8:] if path.startswith('/static/') else None
                    root=ROOT/'static'
                    if not relative or '\\' in relative or any(x in ('.','..','') for x in relative.split('/')): raise APIError(404,'Ressource introuvable.')
                    target=(root/relative).resolve()
                    if not target.is_relative_to(root) or not target.is_file() or target.suffix not in ('.html','.css','.js','.svg','.png','.jpg','.webp','.woff','.woff2'): raise APIError(404,'Ressource introuvable.')
                    status,body,content=200,target.read_bytes(),mimetypes.guess_type(target)[0] or 'application/octet-stream'
                else: raise APIError(404,'Ressource introuvable.')
        except APIError as e: status,body=e.status,{'error':e.message}
        except (ValueError,TypeError,KeyError,UnicodeError,RecursionError): status,body=400,{'error':'Données invalides : schéma, dates, nombres et booléens stricts requis.'}
        except sqlite3.Error: status,body=503,{'error':'Stockage indisponible.'}
        data=body if isinstance(body,bytes) else body.encode() if isinstance(body,str) else json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        headers=[('Content-Type',content),('Content-Length',str(len(data))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),('X-Frame-Options','DENY'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")]+extra
        start_response(f'{status} '+{200:'OK',201:'Created',202:'Accepted',303:'See Other',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Payload Too Large',415:'Unsupported Media Type',429:'Too Many Requests',503:'Service Unavailable'}.get(status,'Error'),headers)
        return [data]

def create_app(store,config): return PilotApplication(store,config)
