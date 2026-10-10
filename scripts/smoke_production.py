"""Real Gunicorn HTTP smoke, random credentials and isolated DB, offline only."""
import http.cookiejar
import hashlib
import copy
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
        token=secrets.token_urlsafe(40); read_token=secrets.token_urlsafe(40)
        integrations=[dict(id='smoke-sync',token_hash=hashlib.sha256(token.encode()).hexdigest(),scopes=['read','import','config']),dict(id='smoke-reader',token_hash=hashlib.sha256(read_token.encode()).hexdigest(),scopes=['read'])]
        env.update(RELAI_INTEGRATIONS_JSON=json.dumps(integrations),RELAI_PASSWORD_HASH=hash_password(password),RELAI_SESSION_SECRET=secrets.token_urlsafe(48),RELAI_ORIGIN=base,RELAI_DB=str(db),RELAI_COOKIE_SECURE='false',RELAI_ENV_FILE=str(tmp/'absent.env'))
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
        def request(path,payload=None,csrf='',origin=True,method=None):
            headers={'Accept':'application/json'}
            if payload is not None:
                headers.update({'Content-Type':'application/json','X-CSRF-Token':csrf})
                if origin: headers['Origin']=base
            req=Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers,method=method)
            try: response=client.open(req,timeout=15)
            except HTTPError as e: response=e
            raw=response.read(); return response.status,json.loads(raw) if response.headers.get_content_type()=='application/json' else raw
        def integration(path,payload=None,method=None,credential=None):
            req=Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Authorization':'Bearer '+(credential or token),'Content-Type':'application/json'},method=method)
            try: response=build_opener().open(req,timeout=15)
            except HTTPError as e: response=e
            return response.status,json.loads(response.read())
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
            assert request('/static/business-ui.js')[0]==200
            # Real HTTP service integration and authenticated manual settings contract.
            code,bootstrap=request('/api/bootstrap'); assert code==200
            from business import default_business
            b=default_business(); t=next(t for t in bootstrap['teachers'] if t['subjects'] and t['pathways'])
            s=next(s for s in bootstrap['schools'] if s['academy']==t['academy'] and s['sector']==t['sector'] and s['lat']==t['lat'] and s['lon']==t['lon'])
            observed=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            b['config'].update(mode='controlled',academy=s['academy'],school_ids=[s['id']],source_reference='Gunicorn smoke fictitious rules',validated_on=observed[:10],state='draft')
            b['zones']=[dict(id='Z_SMOKE',label='Fictitious smoke zone',academy=s['academy'],school_ids=[s['id']],adjacent_zone_ids=[])]
            b['profiles']=[dict(teacher_id=t['id'],status='TZR',rad_school_id=s['id'],zone_ids=['Z_SMOKE'],contract=None,capacity_hours=18,capacity_validated=True,rcd_engagement=None,mobility_modes=['car'],cross_academy=False,source_updated_at=observed,availability=None,timetable=dict(known=True,sessions=[],source_updated_at=observed))]
            payload=dict(document=b,expected_revision=0,confirm_demo=True)
            assert integration('/api/v1/config',credential=read_token)[0]==200
            assert integration('/api/v1/imports/validate',payload,credential=read_token)[0]==403
            assert integration('/api/v1/imports/validate',payload)[0]==200
            assert integration('/api/v1/config')[1]['revision']==0
            assert integration('/api/v1/events')[1]['events']==[]
            payload['idempotency_key']='gunicorn_snapshot_001'
            code,saved=integration('/api/v1/imports/commit',payload); assert code==200 and saved['revision']==1
            assert integration('/api/v1/config')[1]==saved
            assert integration('/api/v1/imports/commit',payload)==(200,saved)
            changed=copy.deepcopy(payload);changed['document']['config']['label']='Different';assert integration('/api/v1/imports/commit',changed)[0]==409
            assert len(integration('/api/v1/events')[1]['events'])==1
            for ref in ('zones','profiles','timetables'):assert integration('/api/v1/reference/'+ref)[1]['revision']==1
            assert integration('/api/v1/events?cursor=v2:0')[0]==400
            assert integration('/api/bootstrap')[0]==403
            n=dict(school_id=s['id'],subject=t['subjects'][0],pathway=next(p for p in t['pathways'] if p in s['pathways']),start_date=t['available_from'],end_date=t['available_from'],hours=6,allow_cross_academy=False,max_travel_minutes=90,mission_type='rectoral',sessions=[dict(date=t['available_from'],start='10:00',end='11:00',timezone='Europe/Paris',school_id=s['id'])])
            code,matched=request('/api/match',n,csrf);assert code==200 and not matched['candidates'] and matched['review']
            bn=dict(n,urgency='Normale',max_distance_km=150)
            code,result=request('/api/batches',{'schema_version':1,'needs':[bn]},csrf);assert code==201;bj=result['job']['id']
            assert request('/api/batches/'+bj+'/run',{},csrf)[0]==202
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                result=request('/api/batches/'+bj)[1]['job']
                if result['status']!='running':break
                time.sleep(.1)
            assert result['counts']['review']==1 and result['counts']['proposed']==0,result
            assert request('/api/business/validate',dict(document=b,expected_revision=1,confirm_demo=True),csrf)[0]==200
            code,manual=request('/api/business/commit',dict(document=b,expected_revision=1,confirm_demo=True),csrf);assert code==200 and manual['revision']==2
            assert request('/api/business')[1]==manual
            assert request('/api/batches/'+bj)[1]['job']['status']=='stale'
            put=dict(document=b,expected_revision=2,confirm_demo=True,idempotency_key='gunicorn_config_003')
            assert request('/api/v1/config',put,csrf='',method='PUT')[0]==403
            assert integration('/api/v1/config',put,method='PUT',credential=read_token)[0]==403
            stale=dict(put,expected_revision=0);assert integration('/api/v1/config',stale,method='PUT')[0]==409
            code,manual=integration('/api/v1/config',put,method='PUT');assert code==200 and manual['revision']==3
            assert integration('/api/v1/config',put,method='PUT')==(200,manual)
            assert len(integration('/api/v1/events')[1]['events'])==3
            # curl contract: Authorization via stdin, not argv, no Cookie/no verbose output.
            curl=subprocess.run(['curl','--fail-with-body','--silent','--show-error','--header','@-',base+'/api/v1/config'],input=('Authorization: Bearer '+read_token+'\n').encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
            assert curl.returncode==0 and json.loads(curl.stdout)==manual
            process.terminate();process.wait(timeout=15)
            from scripts.backup_sqlite import backup
            import shutil
            backup(db,tmp/'restore.sqlite3');shutil.copy2(tmp/'restore.sqlite3',db)
            process=start()
            assert integration('/api/v1/config')[1]==manual
            assert len(integration('/api/v1/events')[1]['events'])==3
            assert request('/api/business')[1]==manual
            assert request('/logout',{},csrf)[0]==200
            assert request('/api/batches/'+j)[0]==401
            print('BUSINESS INTEGRATION SMOKE OK: distinct scoped tokens; dryrun0/commit1/readback/idempotent/no duplicate event/conflict409; draft matching and batch review failclosed; manual CSRF settings2/readback/atomic job stale; HTTP PUT CSRF403/readscope403/stale409/config3/retry200; curl bearer stdin; restart config/events persisted. No secrets printed.')
            print('GUNICORN HTTP SMOKE OK: health200 private401 login200 csrf403 origin403 batch3000 created201/read200/run202 exact0/3000/0 cancel persisted/restart200 logout401; no IGN calls, no assignments.')
        finally:
            if process and process.poll() is None: process.terminate(); process.wait(timeout=15)
            log.close()

if __name__=='__main__': main()
