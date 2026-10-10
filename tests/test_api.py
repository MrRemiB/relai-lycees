import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from app import create_server
from test_matching import SCHOOL, NEED, TEACHER
from scripts.generate_demo import generate_teachers
from test_routing import FakeRouter

class APITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        (root/'static').mkdir()
        (root/'static'/'index.html').write_text('DEMO')
        self.router=FakeRouter()
        self.server=create_server('127.0.0.1',0,db_path=root/'state.sqlite3',school_data={'metadata':{'source':'fixture'},'schools':[SCHOOL,dict(SCHOOL,id='S2',lat=None,lon=None)]},teachers=[TEACHER],static_dir=root/'static',calendar_data={'metadata':{'source':'calendar fixture'},'holidays':[]},router=self.router)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self,path,payload=None,raw=None,content_type='application/json'):
        body=raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(self.base+path,data=body,headers={'Content-Type':content_type} if body is not None else {})
        try:
            with urllib.request.urlopen(req) as response: return response.status,json.loads(response.read())
        except urllib.error.HTTPError as e:
            with e: return e.code,json.loads(e.read())

    def create(self,**changes):
        status,body=self.request('/api/needs',dict(NEED,urgency='Normale',**changes))
        self.assertEqual(status,201,body)
        return body['need']

    def test_route_assignment_unavailable_time_and_persisted_audit(self):
        n=self.create(max_travel_minutes=15)
        path=f"/api/needs/{n['id']}/assign"
        self.assertEqual(self.request('/api/bootstrap')[1]['metadata']['routing']['profile'],'car')
        self.assertEqual(self.request('/api/match',dict(NEED,need_id=n['id'],max_travel_minutes=90))[0],400)
        self.assertEqual(self.request(path,{'teacher_id':TEACHER['id'],'max_travel_minutes':90})[0],400)
        self.router.status='no_route'
        self.assertEqual(self.request(path,{'teacher_id':TEACHER['id']})[0],409)
        self.router.status='ok'; self.router.duration=901
        self.assertEqual(self.request(path,{'teacher_id':TEACHER['id']})[0],409)
        self.router.duration=600
        s,b=self.request(path,{'teacher_id':TEACHER['id'],'max_travel_minutes':15})
        self.assertEqual(s,200); self.assertEqual(b['assignment']['route']['duration_seconds'],600)
        self.assertEqual(self.request('/api/bootstrap')[1]['assignments'][0]['route']['duration_seconds'],600)

    def test_travel_validation_default_and_legacy(self):
        n=self.create(); self.assertEqual(n['max_travel_minutes'],90)
        for value in [True,-1,481,float('inf'),'90']:
            self.assertEqual(self.request('/api/match',dict(NEED,max_travel_minutes=value))[0],400)
        with self.server.store.connect() as db:
            n.pop('max_travel_minutes'); self.server.store.save(db,n)
        self.assertEqual(self.request('/api/match',dict(NEED,need_id=n['id']))[0],200)

    def test_route_failure_api_is_honest_and_assignment_blocked(self):
        def failure(pairs): raise TimeoutError('fixture failure')
        self.router.route_many=failure
        status,result=self.request('/api/match',NEED)
        self.assertEqual(status,200); self.assertFalse(result['candidates'])
        self.assertTrue(result['routing']['partial']); self.assertEqual(result['routing']['unavailable'],1)
        self.assertIsNone(result['excluded'][0]['duration_seconds'])
        n=self.create()
        self.assertEqual(self.request(f"/api/needs/{n['id']}/assign",{'teacher_id':TEACHER['id']})[0],409)
        self.assertEqual(self.request('/api/bootstrap')[1]['assignments'],[])

    def test_routing_outside_write_lock_rechecks_dates_atomically(self):
        n=self.create(); other=self.create()
        original=self.router.route_many
        def intervening(pairs):
            # A separate SQLite writer can change assignments during provider work.
            with self.server.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO assignments(need_id,teacher_id,start_date,end_date,hours,created_at) VALUES(?,?,?,?,?,?)',(other['id'],TEACHER['id'],NEED['end_date'],NEED['end_date'],1,'fixture'))
            return original(pairs)
        self.router.route_many=intervening
        self.assertEqual(self.request(f"/api/needs/{n['id']}/assign",{'teacher_id':TEACHER['id']})[0],409)
        b=self.request('/api/bootstrap')[1]
        self.assertEqual(len(b['assignments']),1)
        self.assertEqual(next(x for x in b['needs'] if x['id']==n['id'])['status'],'open')

    def test_bootstrap_and_calendar(self):
        s,b=self.request('/api/bootstrap'); self.assertEqual(s,200)
        self.assertEqual(b['needs'],[]); self.assertEqual(b['assignments'],[])
        self.assertEqual(b['metadata']['teacher_count'],1); self.assertTrue(b['metadata']['demo'])
        self.assertEqual(b['metadata']['calendar']['source'],'calendar fixture')
        self.assertEqual(self.request('/api/calendar')[1]['holidays'],[])

    def test_create_match_assign_conflict_release_close(self):
        n=self.create(); second=self.create()
        s,b=self.request('/api/match',dict(NEED,need_id=n['id']))
        self.assertEqual(s,200); self.assertEqual(len(b['candidates']),1)
        endpoint=f"/api/needs/{n['id']}"
        s,b=self.request(endpoint+'/assign',{'teacher_id':TEACHER['id'],'max_distance_km':150})
        self.assertEqual(s,200); self.assertEqual(b['need']['status'],'assigned')
        self.assertEqual(self.request(endpoint+'/assign',{'teacher_id':TEACHER['id']})[0],409)
        self.assertEqual(self.request(f"/api/needs/{second['id']}/assign",{'teacher_id':TEACHER['id']})[0],409)
        self.assertEqual(self.request(endpoint+'/close',{})[0],409)
        self.assertEqual(self.request(endpoint+'/release',{})[1]['need']['status'],'open')
        self.assertEqual(self.request(endpoint+'/close',{})[1]['need']['status'],'closed')
        self.assertEqual(self.request(endpoint+'/assign',{'teacher_id':TEACHER['id']})[0],409)
        self.assertEqual(self.request('/api/bootstrap')[1]['assignments'],[])
        self.assertEqual(len(self.request('/api/needs')[1]['needs']),2)

    def test_persistence_across_server_restart(self):
        n=self.create()
        self.request(f"/api/needs/{n['id']}/assign",{'teacher_id':TEACHER['id']})
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        root=Path(self.temp.name)
        self.server=create_server('127.0.0.1',0,db_path=root/'state.sqlite3',school_data={'metadata':{},'schools':[SCHOOL]},teachers=[],static_dir=root/'static',calendar_data={'metadata':{},'holidays':[]},router=self.router)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        s,b=self.request('/api/bootstrap')
        self.assertEqual(s,200)
        self.assertEqual(b['needs'][0]['status'],'assigned')
        self.assertEqual(b['assignments'][0]['teacher_id'],TEACHER['id'])
        self.assertEqual(b['metadata']['teacher_count'],1)

    def test_action_validation_and_unknown_profile(self):
        n=self.create(); path=f"/api/needs/{n['id']}"
        for p in [{'teacher_id':TEACHER['id'],'max_distance_km':False},{'teacher_id':TEACHER['id'],'max_distance_km':-1},{'teacher_id':TEACHER['id'],'extra':1},{}]:
            self.assertEqual(self.request(path+'/assign',p)[0],400)
        self.assertEqual(self.request(path+'/assign',{'teacher_id':'DEMO-9999'})[0],404)
        self.assertEqual(self.request(path+'/release',{})[0],409)
        self.assertEqual(self.request(path+'/close',{'extra':True})[0],400)
        self.assertEqual(self.request('/api/bootstrap')[1]['needs'][0]['status'],'open')

    def test_stored_need_not_spoofable(self):
        n=self.create()
        self.assertEqual(self.request('/api/match',dict(NEED,need_id=n['id'],hours=1))[0],400)
        self.assertEqual(self.request('/api/match',dict(NEED,need_id=999))[0],404)

    def test_need_identifiers_are_bounded_without_state_change(self):
        largest = 9223372036854775807
        before = self.request('/api/bootstrap')[1]
        for identifier in [largest + 1, 10**100]:
            with self.subTest(identifier=identifier, endpoint='match'):
                status, body = self.request('/api/match', dict(NEED, need_id=identifier))
                self.assertEqual(status, 400)
                self.assertIsInstance(body.get('error'), str)
            for action in ['assign', 'release', 'close']:
                with self.subTest(identifier=identifier, action=action):
                    payload = {'teacher_id': TEACHER['id']} if action == 'assign' else {}
                    status, body = self.request(f'/api/needs/{identifier}/{action}', payload)
                    self.assertEqual(status, 400)
                    self.assertIsInstance(body.get('error'), str)
        # Upper boundary remains valid as an integer but is not an existing need.
        self.assertEqual(self.request('/api/match', dict(NEED, need_id=largest))[0], 404)
        self.assertEqual(self.request(f'/api/needs/{largest}/close', {})[0], 404)
        after = self.request('/api/bootstrap')[1]
        self.assertEqual(after['needs'], before['needs'])
        self.assertEqual(after['assignments'], before['assignments'])

    def test_missing_coordinates_and_unknown(self):
        s,b=self.request('/api/match',dict(NEED,school_id='S2'))
        self.assertEqual(s,200); self.assertFalse(b['candidates']); self.assertIsNone(b['excluded'][0]['distance_km'])
        for payload in [dict(NEED,school_id='unknown'),dict(NEED,subject='x'),dict(NEED,hours=True),dict(NEED,hours=float('nan')),dict(NEED,allow_cross_academy='false'),dict(NEED,start_date='invalid')]:
            self.assertEqual(self.request('/api/match',payload)[0],400)
        self.assertEqual(self.request('/api/needs/999/close',{})[0],404)

    def test_body_limits_content_type_and_static_isolation(self):
        self.assertEqual(self.request('/api/match',raw=b'{')[0],400)
        self.assertEqual(self.request('/api/match',raw=b'[]')[0],400)
        self.assertEqual(self.request('/api/match',NEED,content_type='text/plain')[0],415)
        # Reject the declared size before reading/allocating any oversized body.
        import http.client
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.putrequest('POST','/api/match')
        connection.putheader('Content-Type','application/json')
        connection.putheader('Content-Length','1048577')
        connection.endheaders()
        response=connection.getresponse()
        self.assertEqual(response.status,413)
        self.assertIn('error',json.loads(response.read()))
        connection.close()
        for path in ['/data/schools.json','/runtime/relai.sqlite3','/app.py','/CONTRACT.md','/static/../app.py','/static/%2e%2e/app.py']:
            self.assertEqual(self.request(path)[0],404,path)
        with urllib.request.urlopen(self.base+'/') as r: self.assertEqual(r.read(),b'DEMO')

    def test_import_atomic_anonymous_append(self):
        t=dict(TEACHER,id='DEMO-0002',name='Profil démo 0002')
        s,b=self.request('/api/teachers/import',{'confirm_demo':True,'teachers':[t]})
        self.assertEqual(s,200,b); self.assertEqual(b['imported'],1)
        self.assertEqual(self.request('/api/teachers/import',{'confirm_demo':True,'teachers':[t]})[0],409)
        third=dict(t,id='DEMO-0003',name='Profil démo 0003')
        for bad in [dict(t,id='DEMO-0004',name='Real Name'),dict(t,id='DEMO-0004',lat=999),dict(t,id='DEMO-0004',cross_academy='false'),dict(t,id='DEMO-0004',email='private@example.org')]:
            self.assertEqual(self.request('/api/teachers/import',{'confirm_demo':True,'teachers':[third,bad]})[0],400)
        self.assertEqual(self.request('/api/bootstrap')[1]['metadata']['teacher_count'],2)
        self.assertEqual(self.request('/api/teachers/import',{'confirm_demo':False,'teachers':[third]})[0],400)

    def test_concurrent_assignments_only_one_wins(self):
        ids=[self.create()['id'],self.create()['id']]
        results=[]
        barrier=threading.Barrier(2)
        def assign(n):
            barrier.wait(); results.append(self.request(f'/api/needs/{n}/assign',{'teacher_id':TEACHER['id']})[0])
        threads=[threading.Thread(target=assign,args=(n,)) for n in ids]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(len(self.request('/api/bootstrap')[1]['assignments']),1)

class GeneratorTests(unittest.TestCase):
    def test_each_academy_sector_has_broad_subjects(self):
        from matching import SUBJECTS
        schools=[dict(SCHOOL,id=f'{sector}-{i:03d}-{a}',academy=f'A{a:02d}',sector=sector) for a in range(32) for sector in ['Public','Privé'] for i in range(60)]
        teachers=generate_teachers(schools)
        for a in range(32):
            for sector in ['Public','Privé']:
                self.assertEqual({t['subjects'][0] for t in teachers if t['academy']==f'A{a:02d}' and t['sector']==sector},set(SUBJECTS))

    def test_unknown_sector_not_used_as_anchor(self):
        teachers=generate_teachers([SCHOOL,dict(SCHOOL,id='unknown',academy='Unknown',sector=None)])
        self.assertEqual({t['academy'] for t in teachers},{'Dijon'})
        self.assertEqual({t['sector'] for t in teachers},{'Public'})

    def test_deterministic_school_anchored_broad_profiles(self):
        schools=[dict(SCHOOL,id=str(i),academy='Académie '+str(i)) for i in range(31)]
        teachers=generate_teachers(schools)
        self.assertEqual(teachers,generate_teachers(schools)); self.assertEqual(len(teachers),1600)
        self.assertEqual({s['academy'] for s in schools},{t['academy'] for t in teachers})
        self.assertEqual(len({t['id'] for t in teachers}),1600)
        for t in teachers:
            self.assertTrue(t['name'].startswith('Profil démo ')); self.assertEqual(t['lat'],SCHOOL['lat'])

if __name__=='__main__': unittest.main()
