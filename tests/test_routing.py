import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
import matching
from test_matching import NEED, SCHOOL, TEACHER

START=(5.04,47.32)
END=(5.05,47.33)

def response(start=START,end=END,duration=952.4):
    return dict(resource='bdtopo-osrm',resourceVersion='fixture-2026',profile='car',optimization='fastest',distanceUnit='kilometer',timeUnit='second',start=','.join(map(str,start)),end=','.join(map(str,end)),distance=7.6933,duration=duration,geometry=dict(type='LineString',coordinates=[list(start),list(end)]))

class FakeRouter:
    def __init__(self): self.status='ok'; self.duration=600; self.calls=[]
    def route_many(self,pairs):
        self.calls.extend(pairs)
        return [dict(status=self.status,duration_seconds=self.duration,road_distance_km=8,provider='IGN Géoplateforme',resource='bdtopo-osrm',resource_version='fixture',profile='car',optimization='fastest',computed_at='2026-10-09T00:00:00+00:00',cached=False,geometry=dict(type='LineString',coordinates=[list(a),list(b)])) for a,b in pairs]

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.calls=[]
    def tearDown(self): self.temp.cleanup()
    def service(self,transport=None,**kwargs):
        import routing
        def fixture(url,timeout):
            self.calls.append((url,timeout)); q=parse_qs(urlsplit(url).query)
            return response(tuple(map(float,q['start'][0].split(','))),tuple(map(float,q['end'][0].split(','))))
        return routing.RouteService(Path(self.temp.name)/'routes.sqlite3',transport=transport or fixture,**kwargs)
    def test_service_exists(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('routing'),'Real routing adapter is missing')
    def test_exact_units_geometry_cache_and_direction(self):
        s=self.service(); first=s.route_many([(START,END)])[0]
        self.assertEqual(first['status'],'ok'); self.assertEqual(first['duration_seconds'],952.4)
        self.assertEqual(first['road_distance_km'],7.6933); self.assertFalse(first['cached'])
        self.assertTrue(s.route_many([(START,END)])[0]['cached'])
        s.route_many([(END,START),(START,(5.05000001,47.33))]); self.assertEqual(len(self.calls),3)
        q=parse_qs(urlsplit(self.calls[0][0]).query)
        self.assertEqual(q['timeUnit'],['second']); self.assertEqual(q['distanceUnit'],['kilometer'])
        self.assertEqual(q['geometryFormat'],['geojson']); self.assertEqual(self.calls[0][1],6)
    def test_invalid_provider_payloads_never_offer_duration(self):
        for updates in [dict(duration=-1),dict(duration=True),dict(duration=float('nan')),dict(timeUnit='minute'),dict(distanceUnit='meter'),dict(profile='pedestrian'),dict(geometry={'type':'LineString','coordinates':[[999,0],[5,47]]}),dict(start='0,0'),dict(geometry={'type':'Point','coordinates':[5,47]}),dict(geometry={'type':'LineString','coordinates':[[0,0],[5.05,47.33]]})]:
            with self.subTest(updates=updates):
                s=self.service(transport=lambda u,t:dict(response(),**updates),deployment_version=str(updates))
                r=s.route_many([(START,END)])[0]; self.assertEqual(r['status'],'unavailable'); self.assertIsNone(r.get('duration_seconds'))
    def test_no_route_and_transport_failure_explicit(self):
        s=self.service(transport=lambda u,t:{'error':{'code':'NO_ROUTE'}})
        self.assertEqual(s.route_many([(START,END)])[0]['status'],'no_route')
        s=self.service(transport=lambda u,t:(_ for _ in ()).throw(TimeoutError()),deployment_version='other')
        self.assertEqual(s.route_many([(START,END)])[0]['status'],'unavailable')
    def test_budget_cached_entries_do_not_spend_budget(self):
        s=self.service(uncached_budget=1)
        pairs=[(START,END),(START,(5.06,47.33))]
        self.assertEqual([r['status'] for r in s.route_many(pairs)],['ok','deferred'])
        self.assertEqual([r['status'] for r in s.route_many(pairs)],['ok','ok'])
    def test_rate_shared_across_services_and_concurrent_batches(self):
        times=[]; lock=threading.Lock()
        def transport(u,t):
            with lock: times.append(time.monotonic())
            q=parse_qs(urlsplit(u).query)
            return response(tuple(map(float,q['start'][0].split(','))),tuple(map(float,q['end'][0].split(','))))
        a=self.service(transport); b=self.service(transport,deployment_version='b')
        results=[]
        def batch(s): results.append(s.route_many([(START,(5.05+i*.001,47.33)) for i in range(3)]))
        threads=[threading.Thread(target=batch,args=(s,)) for s in [a,b]]
        for t in threads:t.start()
        for t in threads:t.join()
        # Admission guard refuses competing uncached work honestly rather than queue flooding.
        self.assertEqual(sorted([r[0]['status'] for r in results]),['deferred','ok'])
        a.route_many([(START,(5.05+i*.001,47.33)) for i in range(3)])
        b.route_many([(START,(5.05+i*.001,47.33)) for i in range(3)])
        times.sort(); self.assertEqual(len(times),6)
        self.assertTrue(all(y-x>=.24 for x,y in zip(times,times[1:])),times)
    def test_outage_circuit_stops_after_three_failures(self):
        calls=[]
        def failed(u,t): calls.append(u); raise TimeoutError('fixture')
        s=self.service(transport=failed)
        routes=s.route_many([(START,(5.05+i*.0001,47.33)) for i in range(20)])
        self.assertLessEqual(len(calls),3)
        self.assertTrue(all(r['status']=='unavailable' for r in routes))

    def test_cache_ttls_bound_and_deployment_key(self):
        import sqlite3
        s=self.service(cache_limit=2)
        s.route_many([(START,END)])
        with s._connect() as db:
            expires,created=db.execute('SELECT expires,created FROM routes').fetchone()
        self.assertAlmostEqual(expires-created,604800)
        s.route_many([(START,(5.06,47.33)),(START,(5.07,47.33))])
        with s._connect() as db: self.assertEqual(db.execute('SELECT count(*) FROM routes').fetchone()[0],2)
        other=self.service(deployment_version='new')
        self.assertFalse(other.route_many([(START,(5.07,47.33))])[0]['cached'])
        for status,body,ttl in [('no_route',{'error':{'code':'NO_ROUTE'}},3600),('unavailable',{'error':'bad'},30)]:
            other=self.service(transport=lambda u,t:body,deployment_version=status)
            self.assertEqual(other.route_many([(START,END)])[0]['status'],status)
            with other._connect() as db:
                expires,created=db.execute('SELECT expires,created FROM routes WHERE key=?',(other._key((START,END)),)).fetchone()
            self.assertAlmostEqual(expires-created,ttl)

    def test_deadline_returns_explicit_deferred(self):
        s=self.service(batch_deadline=.01)
        import routing
        with patch.object(routing,'_LAST_START',time.monotonic()):
            r=s.route_many([(START,END)])[0]
        self.assertEqual(r['status'],'deferred'); self.assertEqual(len(self.calls),0)

    def test_ranking_exact_seconds_not_geodesic(self):
        class Router(FakeRouter):
            def route_many(self,pairs):
                results=super().route_many(pairs)
                for r,(a,b) in zip(results,pairs): r['duration_seconds']=600.2 if a==START else 600.1
                return results
        self.assertTrue(hasattr(matching,'match_routed_candidates'),'Routed matching wrapper missing')
        r=matching.match_routed_candidates(NEED,SCHOOL,[TEACHER,dict(TEACHER,id='farther',lon=5.05)],[],Router())
        self.assertEqual([c['teacher']['id'] for c in r['candidates']],['farther',TEACHER['id']])
        self.assertEqual(r['candidates'][0]['duration_minutes'],600.1/60)
    def test_eligibility_first_unavailable_partial_and_max(self):
        self.assertTrue(hasattr(matching,'match_routed_candidates'),'Routed matching wrapper missing')
        router=FakeRouter(); router.status='no_route'
        r=matching.match_routed_candidates(NEED,SCHOOL,[TEACHER,dict(TEACHER,id='bad',subjects=['Anglais'])],[],router)
        self.assertEqual(len(router.calls),1); self.assertFalse(r['candidates']); self.assertFalse(r['routing']['partial'])
        router.status='unavailable'; self.assertTrue(matching.match_routed_candidates(NEED,SCHOOL,[TEACHER],[],router)['routing']['partial'])
        router.status='ok'; r=matching.match_routed_candidates(dict(NEED,max_travel_minutes=0),SCHOOL,[TEACHER],[],router)
        self.assertFalse(r['candidates']); self.assertIn('Temps de trajet supérieur au maximum',r['excluded'][0]['reasons'])
        router.duration=0; self.assertTrue(matching.match_routed_candidates(dict(NEED,max_travel_minutes=0),SCHOOL,[TEACHER],[],router)['candidates'])

if __name__=='__main__': unittest.main()
