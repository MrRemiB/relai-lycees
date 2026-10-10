"""Real Gunicorn HTTP smoke, random credentials and isolated DB, offline only."""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError, URLError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from production import hash_password
ROOT=Path(__file__).resolve().parents[1]

def main():
    (ROOT/'runtime').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='http-smoke-',dir=ROOT/'runtime') as tmp:
        tmp=Path(tmp); db=tmp/'pilot.sqlite3'; password=secrets.token_urlsafe(32)
        with socket.socket() as s: s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env=os.environ.copy()
        for k in tuple(env):
            if k.startswith('RELAI_'): del env[k]
        env.update(RELAI_PASSWORD_HASH=hash_password(password),RELAI_SESSION_SECRET=secrets.token_urlsafe(48),RELAI_ORIGIN=base,RELAI_DB=str(db),RELAI_COOKIE_SECURE='false',RELAI_ENV_FILE=str(tmp/'absent.env'))
        cmd=[sys.executable,'-m','gunicorn','-c','gunicorn.conf.py','--bind',f'127.0.0.1:{port}','wsgi:application']
        log=open(tmp/'server.log','w+')
        process=None
        def start():
            p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=log)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if p.poll() is not None:
                    log.seek(0); raise RuntimeError('Gunicorn exited: '+log.read())
                try:
                    if build_opener().open(base+'/health',timeout=1).status==200: return p
                except (URLError,TimeoutError): time.sleep(.1)
            p.terminate(); p.wait(timeout=10); raise RuntimeError('Gunicorn readiness timeout')
        jar=http.cookiejar.CookieJar(); client=build_opener(HTTPCookieProcessor(jar))
        def request(path,payload=None,csrf='',origin=True):
            headers={'Accept':'application/json'}
            if payload is not None:
                headers.update({'Content-Type':'application/json','X-CSRF-Token':csrf})
                if origin: headers['Origin']=base
            req=Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
            try: response=client.open(req,timeout=15)
            except HTTPError as e: response=e
            raw=response.read(); return response.status,json.loads(raw) if response.headers.get_content_type()=='application/json' else raw
        try:
            process=start()
            # Real process ownership check: a second worker on this same DB
            # must fail boot instead of duplicating background work.
            with socket.socket() as s: s.bind(('127.0.0.1',0)); duplicate_port=s.getsockname()[1]
            duplicate_cmd=[sys.executable,'-m','gunicorn','-c','gunicorn.conf.py','--bind',f'127.0.0.1:{duplicate_port}','wsgi:application']
            duplicate=subprocess.run(duplicate_cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
            assert duplicate.returncode!=0 and 'Un seul processus' in duplicate.stdout.decode(),'duplicate worker must fail boot'
            missing_env={k:v for k,v in env.items() if k not in ('RELAI_PASSWORD_HASH','RELAI_SESSION_SECRET')}
            absent=subprocess.run(duplicate_cmd,cwd=ROOT,env=missing_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
            assert absent.returncode!=0 and 'RELAI_PASSWORD_HASH' in absent.stdout.decode(),'missing credentials must fail boot'
            assert request('/health')==(200,{'status':'ok'})
            assert request('/api/bootstrap')[0]==401
            assert request('/static/app.js')[0]==401
            code,data=request('/login',{'password':password}); assert code==200; csrf=data['csrf_token']
            code,data=request('/api/bootstrap'); assert code==200 and data['auth']['role']=='coordinator'
            school=next(s for s in data['schools'] if s['pathways'] and (s['lat'] is None or s['lon'] is None))
            need=dict(school_id=school['id'],subject='Mathématiques',pathway=school['pathways'][0],start_date='2026-10-10',end_date='2026-10-20',hours=12,urgency='Normale',allow_cross_academy=False,max_distance_km=150,max_travel_minutes=90)
            assert request('/api/batches',{'needs':[need]},csrf='',origin=True)[0]==403
            assert request('/api/batches',{'needs':[need]},csrf=csrf,origin=False)[0]==403
            code,data=request('/api/batches',{'needs':[need]*3000},csrf=csrf); assert code==201
            j=data['job']['id']; assert data['job']['counts']==dict(total=3000,proposed=0,deferred=3000,unassigned=0)
            code,data=request('/api/batches/'+j); assert code==200 and len(data['job']['results'])==3000
            assert request('/api/batches/'+j+'/run',{},csrf)[0]==202
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                code,data=request('/api/batches/'+j); assert code==200
                if data['job']['status']!='running': break
                time.sleep(.2)
            assert data['job']['status']=='partial',data['job']['status']
            assert data['job']['counts']==dict(total=3000,proposed=0,deferred=3000,unassigned=0)
            assert request('/api/batches/'+j+'/cancel',{},csrf)[1]['job']['status']=='cancelled'
            process.terminate(); process.wait(timeout=15); process=start()
            code,data=request('/api/batches/'+j); assert code==200 and data['job']['status']=='cancelled'
            assert data['job']['counts']['total']==3000
            from contextlib import closing
            with closing(sqlite3.connect(db)) as sql:
                assert sql.execute('SELECT count(*) FROM assignments').fetchone()[0]==0
                assert sql.execute('SELECT count(*) FROM needs').fetchone()[0]==0
            assert request('/static/server-batch-ui.js')[0]==200
            assert request('/logout',{},csrf)[0]==200
            assert request('/api/batches/'+j)[0]==401
            print('GUNICORN HTTP SMOKE OK: health200 private401 login200 csrf403 origin403 batch3000 created201/read200/run202 exact0/3000/0 cancel persisted/restart200 logout401; no IGN calls, no assignments.')
        finally:
            if process and process.poll() is None: process.terminate(); process.wait(timeout=15)
            log.close()

if __name__=='__main__': main()
