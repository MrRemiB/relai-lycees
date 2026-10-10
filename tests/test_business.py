"""Business persistence, security and assignment race regressions, isolated SQLite."""
import copy
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch
from app import Store,APIError
from business import business_check,default_business,validate_business
from production import create_app,hash_password

FIXTURES=json.loads((Path(__file__).parent/'fixtures/business-parity.json').read_text())

class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.x=copy.deepcopy(FIXTURES[0]); self.s=self.x['school']; self.t=self.x['teacher']; self.n=self.x['need']; self.b=self.x['business']
        stamp=dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        self.b['config']['validated_on']=stamp[:10]; self.b['profiles'][0]['source_updated_at']=stamp; self.b['profiles'][0]['timetable']['source_updated_at']=stamp
        self.store=Store(Path(self.tmp.name)/'db.sqlite3',{'schools':[self.s]},[self.t],{})
        self.tokens={scope:secrets.token_urlsafe(40) for scope in ('read','config','import','all')}
        integrations=[dict(id=scope,token_hash=hashlib.sha256(token.encode()).hexdigest(),scopes=['read','config','import'] if scope=='all' else [scope]) for scope,token in self.tokens.items()]
        self.password=secrets.token_urlsafe(30)
        self.app=create_app(self.store,dict(password_hash=hash_password(self.password),session_secret=secrets.token_urlsafe(40),origin='https://test.example',secure=True,integrations=integrations))
        self.cookie='';self.csrf=''
    def tearDown(self): self.app.batches.wait();self.tmp.cleanup()
    def request(self,path,method='GET',body=None,token=None,cookie=None,csrf=None):
        path,_,query=path.partition('?'); raw=json.dumps(body).encode() if body is not None else b''
        env=dict(PATH_INFO=path,QUERY_STRING=query,REQUEST_METHOD=method,CONTENT_LENGTH=str(len(raw)),CONTENT_TYPE='application/json',HTTP_ORIGIN='https://test.example',HTTP_COOKIE=self.cookie if cookie is None else cookie,HTTP_X_CSRF_TOKEN=self.csrf if csrf is None else csrf,REMOTE_ADDR='127.0.0.1',**{'wsgi.input':io.BytesIO(raw)})
        if token is not None:env['HTTP_AUTHORIZATION']='Bearer '+token
        response={}
        def start(status,headers):response.update(status=int(status.split()[0]),headers=dict(headers))
        raw=b''.join(self.app(env,start));response['body']=json.loads(raw) if response['headers']['Content-Type'].startswith('application/json') else raw.decode()
        return response
    def login(self):
        r=self.request('/login','POST',dict(password=self.password)); self.assertEqual(r['status'],200);self.cookie=r['headers']['Set-Cookie'].split(';')[0]; self.csrf=r['body']['csrf_token']
    def payload(self,revision=0,key=None,document=None):
        p=dict(document=document or self.b,expected_revision=revision,confirm_demo=True)
        if key:p['idempotency_key']=key
        return p
    def commit(self):
        r=self.request('/api/v1/imports/commit','POST',self.payload(key='fixture_key'),token=self.tokens['all']);self.assertEqual(r['status'],200,r);return r['body']
    def test_shared_fixtures(self):
        integral=copy.deepcopy(self.b);integral.update(schema_version=1.0,revision=0.0)
        validate_business(integral,[self.s],[self.t]) # JS Number.isSafeInteger accepts integral JSON numbers.
        astral=copy.deepcopy(self.b);astral['config']['label']='😀'*81
        with self.assertRaises(ValueError):validate_business(astral,[self.s],[self.t]) # Browser limit counts UTF16 units.
        from business import context_fingerprint
        future=copy.deepcopy(FIXTURES[0]);future['business']['config']['validated_on']='2026-10-12'
        a=context_fingerprint([self.s],[self.t],[],future['business'],future['now'])
        b=context_fingerprint([self.s],[self.t],[],future['business'],dt.datetime(2026,10,12,tzinfo=dt.timezone.utc).timestamp())
        self.assertNotEqual(a,b) # Future validation becoming effective also invalidates a job snapshot.
        for x in FIXTURES:
            with self.subTest(x['name']):
                validate_business(x['business'],[x['school']],[x['teacher']]);self.assertEqual(business_check(x['need'],x['school'],x['teacher'],x['business'],x['assignments'],x['now'])['status'],x['status'])
    def test_dryrun_commit_readback_idempotence_conflict(self):
        token=self.tokens['all'];p=self.payload(key='fixture_key')
        r=self.request('/api/v1/imports/validate','POST',self.payload(),token=token);self.assertEqual(r['status'],200);self.assertTrue(r['body']['valid'])
        self.assertEqual(self.request('/api/v1/config',token=token)['body']['revision'],0)
        self.assertEqual(self.request('/api/v1/events',token=token)['body']['events'],[])
        saved=self.commit();self.assertEqual(saved['revision'],1)
        self.assertEqual(self.request('/api/v1/config',token=token)['body'],saved)
        self.assertEqual(self.request('/api/v1/imports/commit','POST',p,token=token)['body'],saved)
        changed=copy.deepcopy(p);changed['document']['config']['label']='Other';self.assertEqual(self.request('/api/v1/imports/commit','POST',changed,token=token)['status'],409)
        self.assertEqual(self.request('/api/v1/imports/commit','POST',self.payload(key='another_key'),token=token)['status'],409)
        events=self.request('/api/v1/events?cursor=v1:0&limit=1',token=token)['body'];self.assertEqual(len(events['events']),1);self.assertFalse(events['has_more']);self.assertEqual(events['events'][0]['actor'],'integration:all')
        for key in ('zones','profiles','timetables'):self.assertEqual(self.request('/api/v1/reference/'+key,token=token)['body']['revision'],1)
    def test_auth_scopes_no_cookie_bypass_and_put_csrf(self):
        self.assertEqual(self.request('/api/v1/config')['status'],401)
        self.assertEqual(self.request('/api/v1/config',token='invalid'*8)['status'],401)
        self.assertEqual(self.request('/api/v1/config',token=self.tokens['read'])['status'],200)
        self.assertEqual(self.request('/api/v1/config','PUT',self.payload(key='config_key'),token=self.tokens['read'])['status'],403)
        self.assertEqual(self.request('/api/v1/config','PUT',self.payload(key='config_key'),token=self.tokens['config'])['status'],200)
        self.assertEqual(self.request('/api/v1/config',token=self.tokens['config'])['status'],403)
        self.assertEqual(self.request('/api/bootstrap',token=self.tokens['all'])['status'],403)
        self.assertEqual(self.request('/api/business/commit','POST',self.payload(1),token=self.tokens['all'])['status'],403)
        self.assertEqual(self.request('/api/v1/config?token=no',token=self.tokens['read'])['status'],403)
        self.login();self.assertEqual(self.request('/api/v1/config',token=self.tokens['all'])['status'],403)
        self.assertEqual(self.request('/api/v1/config','PUT',self.payload(1,key='session_key'),csrf='')['status'],403)
        self.assertEqual(self.request('/api/business/commit','POST',self.payload(1))['status'],200)
        events=self.request('/api/v1/events')['body']['events'];self.assertEqual(events[-1]['actor'],'coordinator')
    def test_strict_validation_atomic_bad_schema_future_envelope(self):
        token=self.tokens['all']
        for change in [lambda b:b.update(schema_version=True),lambda b:b.update(revision=True),lambda b:b['profiles'][0].update(name='not allowed'),lambda b:b['profiles'][0].update(teacher_id='ACTUAL-1'),lambda b:b['profiles'][0].update(capacity_hours=True),lambda b:b['zones'][0].update(adjacent_zone_ids=['Z_UNKNOWN']),lambda b:b['profiles'][0]['timetable'].update(source_updated_at='2026-02-30T00:00:00Z')]:
            b=copy.deepcopy(self.b);change(b)
            self.assertEqual(self.request('/api/v1/imports/commit','POST',self.payload(key='invalid_key',document=b),token=token)['status'],400)
        for expected in [True,-1,'0',None]:
            p=self.payload();p['expected_revision']=expected;self.assertEqual(self.request('/api/v1/imports/validate','POST',p,token=token)['status'],400)
        p=self.payload();p['observed_at']='9999-01-01T00:00:00Z';self.assertEqual(self.request('/api/v1/imports/validate','POST',p,token=token)['status'],400)
        self.assertEqual(self.request('/api/v1/config',token=token)['body']['revision'],0)
        self.assertEqual(self.request('/api/v1/events',token=token)['body']['events'],[])
    def test_sessions_need_strict_and_review_failclosed(self):
        self.commit();self.login()
        b=copy.deepcopy(self.b);b['config']['state']='draft'
        self.assertEqual(self.request('/api/business/commit','POST',self.payload(1,document=b))['status'],200)
        with patch.object(self.store.router,'route_many',return_value=[]) as mock:
            result=self.request('/api/match','POST',self.n);self.assertEqual(result['status'],200);self.assertEqual(len(result['body']['review']),1);self.assertEqual(result['body']['candidates'],[])
            self.assertEqual(mock.call_args.args[0],[])
        n=copy.deepcopy(self.n);n['sessions'][0]['school_id']='0000000A';self.assertEqual(self.request('/api/needs','POST',n)['status'],400)
        need=self.request('/api/needs','POST',self.n)['body']['need']
        with patch.object(self.store.router,'route_many',return_value=[]):self.assertEqual(self.request(f"/api/needs/{need['id']}/assign",'POST',dict(teacher_id=self.t['id'],business_revision=2))['status'],409)
    def test_assignment_config_race_rechecks_and_sessions_readback(self):
        self.commit();self.login();need=self.request('/api/needs','POST',self.n)['body']['need']
        evidence=dict(status='ok',duration_seconds=1,road_distance_km=0,provider='IGN Géoplateforme',resource_version='fixture',computed_at=dt.datetime.now(dt.timezone.utc).isoformat())
        def route(pairs):
            self.store.dispatch('POST','/api/business/commit',self.payload(1))
            return [evidence]
        with patch.object(self.store.router,'route_many',side_effect=route):self.assertEqual(self.request(f"/api/needs/{need['id']}/assign",'POST',dict(teacher_id=self.t['id'],business_revision=1))['status'],409)
        with self.store.connect() as db:self.assertEqual(self.store.assignments(db),[])
        with patch.object(self.store.router,'route_many',return_value=[evidence]):r=self.request(f"/api/needs/{need['id']}/assign",'POST',dict(teacher_id=self.t['id'],business_revision=2))
        self.assertEqual(r['status'],200,r);read=self.request('/api/bootstrap')['body']['assignments'][0];self.assertEqual(read['sessions'],self.n['sessions']);self.assertEqual(read['route_origin_school_id'],self.s['id'])
    def test_batch_current_rules_capacity_sessions_and_atomic_invalidation(self):
        self.commit();self.login();n=dict(self.n,urgency='Normale',max_distance_km=150);second=copy.deepcopy(n);second['sessions'][0].update(start='12:00',end='13:00')
        j=self.request('/api/batches','POST',dict(schema_version=1,needs=[n,second]))['body']['job']['id']
        with patch.object(self.store.router,'route_many',side_effect=lambda pairs:[dict(status='ok',duration_seconds=1,road_distance_km=0,provider='IGN Géoplateforme',resource_version='fixture',computed_at='test') for _ in pairs]):
            self.request('/api/batches/'+j+'/run','POST',{});self.app.batches.wait()
        result=self.request('/api/batches/'+j)['body']['job'];self.assertEqual(result['counts']['proposed'],2,result)
        self.request('/api/business/commit','POST',self.payload(1))
        with self.store.connect() as db:
            row=db.execute('SELECT status,body FROM batch_jobs WHERE id=?',(j,)).fetchone();self.assertEqual(row['status'],'stale');self.assertEqual(json.loads(row['body'])['routes'],{});self.assertTrue(all(r['status']=='deferred' for r in json.loads(row['body'])['results']))
    def test_events_pagination_and_malformed_cursor(self):
        self.login()
        for i in range(3):self.assertEqual(self.request('/api/business/commit','POST',self.payload(i))['status'],200)
        page=self.request('/api/v1/events?limit=2')['body'];self.assertEqual(len(page['events']),2);self.assertTrue(page['has_more']);nextpage=self.request('/api/v1/events?cursor='+page['next_cursor']+'&limit=2')['body'];self.assertEqual(len(nextpage['events']),1);self.assertFalse(nextpage['has_more'])
        for q in ('limit=201','cursor=2','limit=0','cursor=v2:0','limit=2&limit=2','token=secret'):self.assertEqual(self.request('/api/v1/events?'+q)['status'],400)
    def test_legacy_saved_need_accepts_explicit_unknown_mission_from_new_ui(self):
        self.login();legacy={k:v for k,v in self.n.items() if k not in ('mission_type','sessions')}
        need=self.request('/api/needs','POST',legacy)['body']['need']
        request=dict(legacy,need_id=need['id'],mission_type='unknown')
        with patch.object(self.store.router,'route_many',return_value=[dict(status='no_route')]):
            self.assertEqual(self.request('/api/match','POST',request)['status'],200)
        request['mission_type']='RCD'
        self.assertEqual(self.request('/api/match','POST',request)['status'],400)

    def test_utf8_document_byte_boundary_and_http_body_limit(self):
        from business import MAX_BYTES
        raw=json.dumps(self.b,ensure_ascii=False,separators=(',',':'))
        raw+=' '*(MAX_BYTES-len(raw.encode()))
        p=self.payload();p['document']=raw
        self.assertEqual(self.request('/api/v1/imports/validate','POST',p,token=self.tokens['all'])['status'],200)
        p['document']=raw+' '
        self.assertEqual(self.request('/api/v1/imports/validate','POST',p,token=self.tokens['all'])['status'],413)
        p['document']=' '*3_000_001
        self.assertEqual(self.request('/api/v1/imports/validate','POST',p,token=self.tokens['all'])['status'],413)
        self.assertEqual(self.request('/api/v1/config',token=self.tokens['all'])['body']['revision'],0)

    def test_duplicate_json_and_unknown_envelope_rejected_without_events(self):
        duplicate=json.dumps(self.b).replace('"schema_version": 1','"schema_version": 1, "schema_version": 1')
        p=self.payload();p['document']=duplicate
        self.assertEqual(self.request('/api/v1/imports/validate','POST',p,token=self.tokens['all'])['status'],400)
        p=self.payload();p['callback_url']='http://127.0.0.1/'
        self.assertEqual(self.request('/api/v1/imports/validate','POST',p,token=self.tokens['all'])['status'],400)
        self.assertEqual(self.request('/api/v1/events',token=self.tokens['all'])['body']['events'],[])

    def test_concurrent_config_compare_and_swap_single_event(self):
        from concurrent.futures import ThreadPoolExecutor
        def commit(i):return self.request('/api/v1/imports/commit','POST',self.payload(key=f'concurrent_{i}'),token=self.tokens['all'])['status']
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(commit,[1,2]))
        self.assertEqual(sorted(statuses),[200,409]);self.assertEqual(self.request('/api/v1/config',token=self.tokens['all'])['body']['revision'],1)
        self.assertEqual(len(self.request('/api/v1/events',token=self.tokens['all'])['body']['events']),1)

    def test_known_intersite_assignment_and_nonparis_sessions_review(self):
        second=dict(self.s,id='0210002B',lat=47.31)
        self.store.schools.append(second);self.store.school_index[second['id']]=second
        self.b['config']['school_ids'].append(second['id']);self.b['zones'][0]['school_ids'].append(second['id']);self.commit();self.login()
        prior=dict(self.n,school_id=second['id'],sessions=[dict(self.n['sessions'][0],school_id=second['id'],start='08:00',end='09:00')])
        need=self.request('/api/needs','POST',prior)['body']['need']
        route=dict(status='ok',duration_seconds=1,road_distance_km=1,provider='IGN Géoplateforme',resource_version='fixture',computed_at=dt.datetime.now(dt.timezone.utc).isoformat())
        with patch.object(self.store.router,'route_many',return_value=[route]):r=self.request(f"/api/needs/{need['id']}/assign",'POST',dict(teacher_id=self.t['id'],business_revision=1))
        self.assertEqual(r['status'],200,r)
        with patch.object(self.store.router,'route_many',return_value=[]):
            matched=self.request('/api/match','POST',self.n)['body'];self.assertEqual(matched['candidates'],[]);self.assertIn('Transition intersites',matched['review'][0]['reasons'][0])
            n=copy.deepcopy(self.n);n['sessions'][0]['timezone']='UTC';matched=self.request('/api/match','POST',n)['body'];self.assertEqual(matched['candidates'],[]);self.assertTrue(matched['review'])

    def test_openapi_declares_installed_closed_schema_and_routes(self):
        spec=json.loads((Path(__file__).parents[1]/'openapi.json').read_text());self.assertEqual(spec['openapi'],'3.1.0')
        for path in ['/api/v1/config','/api/v1/reference/zones','/api/v1/reference/profiles','/api/v1/reference/timetables','/api/v1/imports/validate','/api/v1/imports/commit','/api/v1/events']:self.assertIn(path,spec['paths'])
        schemas=spec['components']['schemas'];self.assertFalse(schemas['Profile']['additionalProperties']);self.assertEqual(set(schemas['Profile']['required']),set(self.b['profiles'][0]));self.assertEqual(schemas['Business']['properties']['profiles']['maxItems'],5000)
        docs=(Path(__file__).parents[1]/'BUSINESS_SERVER.md').read_text()
        for text in ['expected_revision','idempotency_key','observed_at','0600','read','config','import','Europe/Paris','3000']:self.assertIn(text,docs)

    def test_integration_setup_no_fixed_secret_and_hash_readback(self):
        from scripts.setup_integration import setup
        server=Path(self.tmp.name)/'server.json';client=Path(self.tmp.name)/'client.env';setup(server,client,'sync',['read','import'])
        self.assertEqual(server.stat().st_mode&0o777,0o600);self.assertEqual(client.stat().st_mode&0o777,0o600)
        token=client.read_text().strip().split('=',1)[1];self.assertNotIn(token,server.read_text());self.assertEqual(json.loads(server.read_text())[0]['token_hash'],hashlib.sha256(token.encode()).hexdigest())
        with self.assertRaises(FileExistsError):setup(server,client,'sync',['read'])

if __name__=='__main__':unittest.main()
