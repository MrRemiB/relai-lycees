"""IGN fastest-car routes; bounded process-wide admission, rate and workers.
Only endpoint coordinates are sent. No fabricated route or duration fallback.
"""
import datetime as dt
from contextlib import contextmanager
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from matching import coordinates, distance_km, number

PROVIDER='IGN Géoplateforme'
SOURCE_URL='https://data.geopf.fr/navigation/itineraire'
RESOURCE='bdtopo-osrm'
METADATA=dict(provider=PROVIDER,profile='car',traffic=False,source_url=SOURCE_URL,
    max_travel_minutes_default=90,rate_limit_rps=4,timeout_seconds=6,
    batch_deadline_seconds=30,uncached_budget=80,
    notice='Coordonnées des bases fictives et lycées transmises au service IGN ; aucun nom, discipline, date ou contact transmis. Estimations en voiture sans trafic en temps réel.')
_EXECUTOR=ThreadPoolExecutor(max_workers=4,thread_name_prefix='ign-route')
_ADMISSION=threading.BoundedSemaphore(1)
_RATE_LOCK=threading.Lock()
_LAST_START=0.0


def _slot(deadline):
    global _LAST_START
    with _RATE_LOCK:
        delay=max(0,.25-(time.monotonic()-_LAST_START))
        if time.monotonic()+delay>=deadline: return False
        if delay: time.sleep(delay)
        _LAST_START=time.monotonic()
        return True


def _transport(url,timeout):
    request=Request(url,headers={'Accept':'application/json','User-Agent':'Relai-Lycees-demo/1.0'})
    try:
        with urlopen(request,timeout=timeout) as response:
            raw=response.read(4_000_001)
    except HTTPError as exc:
        # Parse only bounded JSON structured no-route codes; never reflect provider text.
        if exc.code not in (400,404,422): raise
        raw=exc.read(65537)
        if len(raw)>65536: raise ValueError('Provider response too large')
    if len(raw)>4_000_000: raise ValueError('Provider response too large')
    return json.loads(raw)


def _point(value):
    if not isinstance(value,(list,tuple)) or len(value)!=2: raise ValueError('Invalid point')
    if not coordinates(value[1],value[0]): raise ValueError('Missing point')
    return value


def _near(a,b): return distance_km(a[1],a[0],b[1],b[0])<=1


def _validate(body,start,end):
    if not isinstance(body,dict): raise ValueError('Invalid response')
    error=body.get('error')
    code=error.get('code') if isinstance(error,dict) else body.get('code')
    if code in ('NO_ROUTE','NoRoute','NO_PATH','POINT_NOT_FOUND'):
        return dict(status='no_route',duration_seconds=None)
    if error: raise ValueError('Provider error')
    for key,expected in [('resource',RESOURCE),('profile','car'),('optimization','fastest'),('distanceUnit','kilometer'),('timeUnit','second'),('crs','EPSG:4326')]:
        if body.get(key,expected)!=expected: raise ValueError('Unexpected routing units/profile')
    duration=number(body.get('duration'),'Duration',0,1e9)
    distance=number(body.get('distance'),'Road distance',0,1e7)
    geometry=body.get('geometry')
    if not isinstance(geometry,dict) or geometry.get('type')!='LineString': raise ValueError('Missing road geometry')
    points=geometry.get('coordinates')
    if not isinstance(points,list) or not 2<=len(points)<=25000: raise ValueError('Invalid geometry length')
    for p in points: _point(p)
    for field,original,endpoint in [('start',start,points[0]),('end',end,points[-1])]:
        snapped=body.get(field)
        if not isinstance(snapped,str): raise ValueError('Missing snapped endpoint')
        snapped=_point([float(v) for v in snapped.split(',')])
        if not _near(snapped,original) or not _near(endpoint,original): raise ValueError('Snap exceeds 1 km')
    version=body.get('resourceVersion')
    if not isinstance(version,str) or not 1<=len(version)<=120: raise ValueError('Missing resource version')
    return dict(status='ok',duration_seconds=duration,road_distance_km=distance,
        geometry=dict(type='LineString',coordinates=points),resource_version=version)


class RouteService:
    def __init__(self,cache_path,*,transport=None,uncached_budget=80,batch_deadline=30,cache_limit=10000,deployment_version='ign-car-v1'):
        self.path=str(cache_path); Path(cache_path).parent.mkdir(parents=True,exist_ok=True)
        self.transport=transport or _transport
        self.budget=min(80,max(0,uncached_budget)); self.deadline=min(30,max(0,batch_deadline))
        self.limit=max(1,min(10000,cache_limit)); self.version=deployment_version
        self.lock=threading.Lock(); self.failures=0; self.circuit_until=0
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS routes(key TEXT PRIMARY KEY, body TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL)')

    @contextmanager
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=2)
        try:
            with db: yield db
        finally: db.close()

    def _key(self,pair):
        return json.dumps([self.version,RESOURCE,'car','fastest',pair],separators=(',',':'),allow_nan=False)

    def _cached(self,key):
        with self.lock,self._connect() as db:
            row=db.execute('SELECT body FROM routes WHERE key=? AND expires>?',(key,time.time())).fetchone()
        return dict(json.loads(row[0]),cached=True) if row else None

    def _save(self,key,result):
        ttl=604800 if result['status']=='ok' else 3600 if result['status']=='no_route' else 30
        with self.lock,self._connect() as db:
            now=time.time()
            db.execute('DELETE FROM routes WHERE expires<=?',(now,))
            db.execute('INSERT OR REPLACE INTO routes VALUES(?,?,?,?)',(key,json.dumps(result,allow_nan=False),now+ttl,now))
            db.execute('DELETE FROM routes WHERE key IN (SELECT key FROM routes ORDER BY created DESC LIMIT -1 OFFSET ?)',(self.limit,))

    def _calculate(self,pair,key,deadline):
        with self.lock:
            if time.monotonic()<self.circuit_until: return dict(status='unavailable',duration_seconds=None,cached=False)
        if not _slot(deadline): return dict(status='deferred',duration_seconds=None,cached=False)
        with self.lock:
            if time.monotonic()<self.circuit_until: return dict(status='unavailable',duration_seconds=None,cached=False)
        start,end=pair
        query=dict(resource=RESOURCE,profile='car',optimization='fastest',start=','.join(map(str,start)),end=','.join(map(str,end)),geometryFormat='geojson',getSteps='false',getBbox='true',distanceUnit='kilometer',timeUnit='second',crs='EPSG:4326')
        try:
            result=_validate(self.transport(SOURCE_URL+'?'+urlencode(query),min(6,max(.001,deadline-time.monotonic()))),start,end)
        except Exception:
            result=dict(status='unavailable',duration_seconds=None)
        result.update(provider=PROVIDER,resource=RESOURCE,profile='car',optimization='fastest',computed_at=dt.datetime.now(dt.timezone.utc).isoformat(),cached=False)
        with self.lock:
            if result['status']=='unavailable':
                self.failures+=1
                if self.failures>=3: self.circuit_until=time.monotonic()+30
            else: self.failures=0
        self._save(key,result)
        return result

    def route_many(self,pairs):
        pairs=list(pairs)
        for a,b in pairs: _point(a); _point(b)
        keys=[self._key(p) for p in pairs]
        results=[self._cached(k) for k in keys]
        pending={}
        for i,(p,k,r) in enumerate(zip(pairs,keys,results)):
            if r is None: pending.setdefault(k,[p,[]])[1].append(i)
        if not pending: return results
        deferred=dict(status='deferred',duration_seconds=None,cached=False)
        for i,r in enumerate(results):
            if r is None: results[i]=dict(deferred)
        # Cached work never waits for another batch. One live batch process-wide.
        if not _ADMISSION.acquire(blocking=False): return results
        deadline=time.monotonic()+self.deadline
        jobs=iter(list(pending.items())[:self.budget]); job_lock=threading.Lock()
        def worker():
            while time.monotonic()<deadline:
                with job_lock:
                    job=next(jobs,None)
                if job is None: return
                key,(pair,indices)=job
                result=self._cached(key) or self._calculate(pair,key,deadline)
                if time.monotonic()<=deadline:
                    with job_lock:
                        for i in indices: results[i]=result
        futures=[]
        try:
            futures=[_EXECUTOR.submit(worker) for _ in range(min(4,len(pending),self.budget))]
            wait(futures,timeout=max(0,deadline-time.monotonic()))
            # Freeze response at deadline; in-flight urllib calls have finite timeout.
            with job_lock: snapshot=[dict(r) for r in results]
        finally:
            # Keep admission until the last timed-out worker actually exits.
            remaining=[f for f in futures if not f.done()]
            if remaining:
                def release_when_done(_):
                    with job_lock:
                        if all(f.done() for f in futures) and not released[0]:
                            released[0]=True; _ADMISSION.release()
                released=[False]
                for f in remaining: f.add_done_callback(release_when_done)
            else: _ADMISSION.release()
        return snapshot
