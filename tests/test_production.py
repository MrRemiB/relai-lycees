"""Offline pilot security and durable batch integration; no IGN calls."""
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from app import Store, APIError
from test_matching import SCHOOL, NEED, TEACHER

class ProductionTests(unittest.TestCase):
    def setUp(self):
        import production
        self.p=production
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'pilot.sqlite3',{'schools':[SCHOOL]},[TEACHER],{})
        self.config=dict(password_hash=production.hash_password('test-only-random-password'),session_secret='x'*48,origin='https://pilot.example',secure=True)
        self.app=production.create_app(self.store,self.config)
        self.cookie=''; self.csrf=''
    def tearDown(self):
        self.app.batches.wait(); self.tmp.cleanup()
    def request(self,path,method='GET',body=None,origin='https://pilot.example',csrf=True):
        raw=json.dumps(body).encode() if body is not None else b''
        env=dict(PATH_INFO=path,REQUEST_METHOD=method,CONTENT_LENGTH=str(len(raw)),CONTENT_TYPE='application/json',HTTP_COOKIE=self.cookie,REMOTE_ADDR='127.0.0.1',HTTP_HOST='pilot.example',**{'wsgi.input':io.BytesIO(raw)})
        if origin: env['HTTP_ORIGIN']=origin
        if csrf: env['HTTP_X_CSRF_TOKEN']=self.csrf
        response={}
        def start(status,headers): response.update(status=int(status.split()[0]),headers=dict(headers))
        data=b''.join(self.app(env,start)); response['body']=json.loads(data) if response['headers']['Content-Type'].startswith('application/json') else data.decode()
        return response
    def login(self):
        r=self.request('/login','POST',{'password':'test-only-random-password'})
        self.assertEqual(r['status'],200)
        self.cookie=r['headers']['Set-Cookie'].split(';')[0]; self.csrf=r['body']['csrf_token']; return r
    def need(self,**updates): return dict(NEED,urgency='Normale',max_distance_km=150,max_travel_minutes=90,**updates)
    def batch(self,needs=None):
        r=self.request('/api/batches','POST',{'needs':needs or [self.need()]})
        self.assertEqual(r['status'],201); return r['body']['job']['id']
    def job(self,j): return self.request('/api/batches/'+j)['body']['job']
    def runjob(self,j):
        r=self.request('/api/batches/'+j+'/run','POST',{})
        self.assertEqual(r['status'],202); self.app.batches.wait(); return self.job(j)
    def test_missing_secrets_fail_start(self):
        with patch.dict('os.environ',{},clear=True), self.assertRaises(ValueError): self.p.from_environment()
        for changes in [dict(password_hash='bad'),dict(session_secret='short'),dict(origin='http://pilot.example')]:
            with self.assertRaises(ValueError): self.p.create_app(self.store,dict(self.config,**changes))
    def test_private_routes_and_assets_are_protected_health_minimal(self):
        for path in ['/','/static/app.js','/api/bootstrap','/api/batches','/data/schools.json','/app.py']:
            self.assertEqual(self.request(path)['status'],401)
        r=self.request('/health'); self.assertEqual(r['body'],{'status':'ok'})
    def test_login_cookie_csrf_origin_logout(self):
        self.assertEqual(self.request('/login','POST',{'password':'bad'})['status'],401)
        self.assertEqual(self.request('/login','POST',{'password':'test-only-random-password'},origin='https://evil.example')['status'],403)
        r=self.login()
        for attr in ['HttpOnly','SameSite=Strict','Secure']: self.assertIn(attr,r['headers']['Set-Cookie'])
        bootstrap=self.request('/api/bootstrap')['body']; self.assertEqual(bootstrap['csrf_token'],self.csrf)
        self.assertEqual(bootstrap['auth']['role'],'coordinator')
        for origin,csrf in [('https://evil.example',True),(None,True),('https://pilot.example',False)]:
            self.assertEqual(self.request('/api/needs','POST',NEED,origin=origin,csrf=csrf)['status'],403)
        self.assertEqual(self.request('/api/needs','POST',NEED)['status'],201)
        self.assertEqual(self.request('/logout','POST',{})['status'],200)
        self.assertEqual(self.request('/api/bootstrap')['status'],401)
    def test_session_tamper_and_expiry(self):
        self.login(); self.cookie+='tamper'; self.assertEqual(self.request('/api/bootstrap')['status'],401)
        self.login()
        with self.store.connect() as db: db.execute('UPDATE pilot_sessions SET expires=0')
        self.assertEqual(self.request('/api/bootstrap')['status'],401)
    def test_atomic_schema_limit_3000_persistent(self):
        self.login()
        for needs in [[],[self.need()]*3001,[self.need(),dict(self.need(),hours=True)],[dict(self.need(),personal='no')],[dict(self.need(),max_distance_km=-1)],[dict(self.need(),urgency='bad')]]:
            self.assertEqual(self.request('/api/batches','POST',{'needs':needs})['status'],400)
        with self.store.connect() as db: self.assertEqual(db.execute('SELECT count(*) FROM batch_jobs').fetchone()[0],0)
        j=self.batch([self.need() for _ in range(3000)])
        self.assertEqual(self.job(j)['counts'],dict(total=3000,proposed=0,deferred=3000,unassigned=0))
        other=self.p.create_app(self.store,self.config)
        self.assertEqual(other.batches.get(j)['counts']['total'],3000)
        with self.store.connect() as db: self.assertEqual(len(self.store.needs(db)),0)
    def test_real_route_evidence_priority_conflicts_no_auto_assignment(self):
        self.login(); j=self.batch([self.need(),dict(self.need(),urgency='Urgente')])
        def routes(pairs): return [dict(status='ok',duration_seconds=321,road_distance_km=4,provider='IGN Géoplateforme',resource_version='fixture',computed_at='2026-10-10T00:00:00+00:00') for _ in pairs]
        with patch.object(self.store.router,'route_many',side_effect=routes): result=self.runjob(j)
        self.assertEqual(result['counts'],dict(total=2,proposed=1,deferred=0,unassigned=1))
        self.assertEqual(result['results'][1]['teacher_id'],TEACHER['id'])
        self.assertEqual(result['results'][1]['route']['duration_seconds'],321)
        with self.store.connect() as db: self.assertEqual(self.store.assignments(db),[])
    def test_unknown_routes_defer_then_resume(self):
        self.login(); j=self.batch()
        with patch.object(self.store.router,'route_many',return_value=[dict(status='unavailable')]): r=self.runjob(j)
        self.assertEqual(r['counts']['deferred'],1); self.assertEqual(r['status'],'partial')
        with patch.object(self.store.router,'route_many',return_value=[dict(status='no_route')]): r=self.runjob(j)
        self.assertEqual(r['counts']['unassigned'],1)
    def test_snapshot_change_invalidates_before_read_and_resume(self):
        self.login(); j=self.batch()
        ok=dict(status='ok',duration_seconds=60,road_distance_km=1,provider='IGN Géoplateforme',resource_version='fixture',computed_at='now')
        with patch.object(self.store.router,'route_many',return_value=[ok]): self.assertEqual(self.runjob(j)['counts']['proposed'],1)
        self.store.dispatch('POST','/api/needs',NEED)
        with self.store.connect() as db:
            db.execute("INSERT INTO assignments(need_id,teacher_id,start_date,end_date,hours,created_at) VALUES(1,?,?,?,?,?)",(TEACHER['id'],NEED['start_date'],NEED['end_date'],12,'now'))
        r=self.job(j); self.assertEqual(r['status'],'stale'); self.assertEqual(r['counts']['proposed'],0)
        with patch.object(self.store.router,'route_many') as mock: r=self.runjob(j)
        self.assertEqual(r['counts']['unassigned'],1); mock.assert_not_called()
    def test_cancel_persists_and_restart_resume(self):
        self.login(); j=self.batch(); entered=threading.Event(); release=threading.Event()
        def block(pairs): entered.set(); release.wait(3); return [dict(status='no_route') for _ in pairs]
        with patch.object(self.store.router,'route_many',side_effect=block):
            self.assertEqual(self.request('/api/batches/'+j+'/run','POST',{})['status'],202)
            self.assertTrue(entered.wait(3)); self.assertEqual(self.request('/api/batches/'+j+'/cancel','POST',{})['status'],200)
            release.set(); self.app.batches.wait()
        self.assertEqual(self.job(j)['status'],'cancelled')
        other=self.p.create_app(self.store,self.config); self.assertEqual(other.batches.get(j)['status'],'cancelled')
        with patch.object(self.store.router,'route_many',return_value=[dict(status='no_route')]): self.runjob(j)
        self.assertEqual(self.job(j)['counts']['unassigned'],1)
    def test_credential_setup_masks_and_refuses_overwrite(self):
        from scripts.setup_credentials import setup
        path=Path(self.tmp.name)/'pilot.env'
        with patch('sys.stdin.isatty',return_value=True), patch('getpass.getpass',side_effect=['long-test-password-only','long-test-password-only']):
            setup(path,'https://pilot.example',Path(self.tmp.name)/'db.sqlite3')
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertNotIn('long-test-password-only',path.read_text())
        with self.assertRaises(FileExistsError): setup(path,'https://pilot.example',Path(self.tmp.name)/'db.sqlite3')
    def test_backup_is_consistent_and_verified(self):
        from scripts.backup_sqlite import backup
        self.login(); j=self.batch(); target=Path(self.tmp.name)/'backup.sqlite3'
        backup(self.store.path,target)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(target)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT id FROM batch_jobs').fetchone()[0],j)
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
    def test_unknown_school_evidence_defers_and_expired_routes_stale(self):
        self.login(); original=self.store.school_index['S1']
        self.store.school_index['S1']=dict(original,lat=None,lon=None)
        j=self.batch()
        with patch.object(self.store.router,'route_many') as mock: r=self.runjob(j)
        self.assertEqual(r['counts']['deferred'],1); mock.assert_not_called()
        self.store.school_index['S1']=original
        j=self.batch(); ok=dict(status='ok',duration_seconds=60,road_distance_km=1,provider='IGN Géoplateforme',resource_version='fixture',computed_at='now')
        with patch.object(self.store.router,'route_many',return_value=[ok]): self.runjob(j)
        with self.store.connect() as db:
            body=json.loads(db.execute('SELECT body FROM batch_jobs WHERE id=?',(j,)).fetchone()[0])
            for route in body['routes'].values(): route['expires']=0
            db.execute('UPDATE batch_jobs SET body=? WHERE id=?',(json.dumps(body),j))
        self.assertEqual(self.job(j)['status'],'stale'); self.assertEqual(self.job(j)['counts']['proposed'],0)
    def test_progressive_pass_moves_beyond_unknown_first80(self):
        self.login(); teachers=[dict(TEACHER,id=f'DEMO-{i:04}',lon=5.04+i*.0001) for i in range(100)]
        with self.store.connect() as db:
            db.execute('DELETE FROM teachers'); db.executemany('INSERT INTO teachers VALUES(?,?)',[(t['id'],json.dumps(t)) for t in teachers])
        j=self.batch(); passes=[]
        def routes(pairs):
            passes.append({json.dumps(p) for p in pairs}); return [dict(status='deferred') for _ in pairs]
        with patch.object(self.store.router,'route_many',side_effect=routes): self.runjob(j); self.runjob(j)
        self.assertEqual(len(passes[0]),80); self.assertTrue(passes[1]-passes[0],'resume must progress past unavailable first targets')
    def test_async3000_results_exact_counts_and_conflicts(self):
        self.login(); j=self.batch([self.need() for _ in range(3000)])
        route=dict(status='ok',duration_seconds=45,road_distance_km=1,provider='IGN Géoplateforme',resource_version='fixture',computed_at='now')
        with patch.object(self.store.router,'route_many',return_value=[route]): r=self.runjob(j)
        self.assertEqual(r['status'],'completed'); self.assertEqual(r['progress']['done'],3000)
        self.assertEqual(r['counts'],dict(total=3000,proposed=1,deferred=0,unassigned=2999))
        self.assertEqual(len(r['results']),3000)
    def test_context_changed_during_route_and_competing_run(self):
        self.login(); j=self.batch(); j2=self.batch(); entered=threading.Event(); release=threading.Event()
        def block(pairs): entered.set(); release.wait(3); return [dict(status='no_route')]
        with patch.object(self.store.router,'route_many',side_effect=block):
            self.request('/api/batches/'+j+'/run','POST',{})
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.request('/api/batches/'+j2+'/run','POST',{})['status'],409)
            with self.store.connect() as db: db.execute('UPDATE teachers SET body=?',(json.dumps(dict(TEACHER,capacity_hours=20)),))
            release.set(); self.app.batches.wait()
        self.assertEqual(self.job(j)['status'],'stale'); self.assertEqual(self.job(j)['counts']['proposed'],0)
    def test_auth_rate_limit_and_authenticated_static_isolation(self):
        self.login()
        for path in ['/app.py','/data/schools.json','/static/../production.py','/static/%2e%2e/production.py','/runtime/pilot.sqlite3']:
            self.assertEqual(self.request(path)['status'],404)
        for _ in range(9): self.assertEqual(self.request('/login','POST',{'password':'wrong'})['status'],401)
        self.assertEqual(self.request('/login','POST',{'password':'wrong'})['status'],429)
    def test_global_pass_route_budget_and_job_restart(self):
        self.login(); teachers=[dict(TEACHER,id=f'DEMO-{i:04}',lon=5.04+i*.0001) for i in range(100)]
        with self.store.connect() as db:
            db.execute('DELETE FROM teachers'); db.executemany('INSERT INTO teachers VALUES(?,?)',[(t['id'],json.dumps(t)) for t in teachers])
        j=self.batch()
        def routes(pairs):
            self.assertLessEqual(len(pairs),80); return [dict(status='deferred') for _ in pairs]
        with patch.object(self.store.router,'route_many',side_effect=routes) as mock: self.runjob(j)
        self.assertEqual(mock.call_count,1)
        with self.store.connect() as db: db.execute("UPDATE batch_jobs SET status='running' WHERE id=?",(j,))
        other=self.p.create_app(self.store,self.config); self.assertEqual(other.batches.get(j)['status'],'interrupted')

if __name__=='__main__': unittest.main()
