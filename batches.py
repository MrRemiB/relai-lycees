"""Durable proposal-only pilot jobs. One bounded IGN pass per explicit run."""
import hashlib
import json
import secrets
import threading
import time
from collections import Counter
from app import APIError
from matching import match_candidates, validate_need
from business import effective_teachers,context_fingerprint,business_check

FIELDS={'school_id','subject','pathway','start_date','end_date','hours','urgency','allow_cross_academy','max_distance_km','max_travel_minutes'}
def encoded(value): return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def validate_batch(payload,schools):
    if not isinstance(payload,dict) or set(payload) not in ({'needs'},{'schema_version','needs'}) or ('schema_version' in payload and (type(payload['schema_version']) not in (int,float) or payload['schema_version']!=1)): raise ValueError('Objet {needs} strict requis.')
    items=payload['needs']
    if not isinstance(items,list) or not 1<=len(items)<=3000: raise ValueError('Lot de 1 à 3000 besoins requis.')
    result=[]
    for n in items:
        if not isinstance(n,dict) or not FIELDS<=set(n) or set(n)-FIELDS-{'mission_type','sessions'}: raise ValueError('Schéma de besoin de lot strict requis (urgence et rayon inclus).')
        validate_need({k:v for k,v in n.items() if k!='max_distance_km'},schools,creation=True)
        validate_need({k:v for k,v in n.items() if k!='urgency'},schools)
        result.append(dict(n))
    return result

def pending(needs,reason='Calcul requis'):
    return [dict(n,row=i+2,status='deferred',reason=reason,teacher_id='',duration_seconds=None,route=None,partial=True) for i,n in enumerate(needs)]
def counts(rows):
    c=Counter(r['status'] for r in rows)
    return dict(total=len(rows),proposed=c['proposed'],deferred=c['deferred'],unassigned=c['unassigned'],**({'review':c['review']} if any('review_flags' in r for r in rows) else {}))

def controlled_plan(needs,edges,routes,business,teachers,assignments,schools,reviews,exclusions):
    """Proposals use the same check as actual assignment, including previous proposals."""
    ts={t['id']:t for t in teachers}; chosen={}; trial_reviews={}
    usable=[[e for e in es if e['key'] in routes and routes[e['key']]['expires']>time.time() and routes[e['key']]['status']=='ok' and routes[e['key']]['duration_seconds']<=n['max_travel_minutes']*60] for n,es in zip(needs,edges)]
    for es in usable: es.sort(key=lambda e:(routes[e['key']]['duration_seconds'],routes[e['key']]['road_distance_km'],-e['capacity'],e['teacher_id']))
    def check(i,e,skip=()):
        local=list(assignments)+[dict(needs[j],teacher_id=c['teacher_id']) for j,c in chosen.items() if j not in skip and j!=i]
        return business_check(needs[i],schools[needs[i]['school_id']],ts[e['teacher_id']],business,local)
    order=sorted(range(len(needs)),key=lambda i:(0 if business['config']['priority']=='scarcity' else needs[i]['urgency']!='Urgente',len(usable[i]),needs[i]['start_date'],i))
    for i in order:
        for e in usable[i]:
            r=check(i,e)
            if r['status']=='eligible': chosen[i]=e; break
            if r['status']=='review': trial_reviews[i]=r['reasons']
        if i in chosen: continue
        # Bounded augmentation, rechecking both moved and newly proposed missions.
        for e in usable[i]:
            blockers=[j for j,c in chosen.items() if c['teacher_id']==e['teacher_id']]
            if len(blockers)!=1: continue
            j=blockers[0]
            if check(i,e,(j,))['status']!='eligible': continue
            for alt in usable[j]:
                if alt['teacher_id']==e['teacher_id'] or check(j,alt,(j,))['status']!='eligible': continue
                old=chosen[j]; chosen[j]=alt
                if check(i,e)['status']=='eligible': chosen[i]=e; break
                chosen[j]=old
            if i in chosen: break
    rows=[]
    for i,n in enumerate(needs):
        e=chosen.get(i); unknown=any(v['key'] not in routes or routes[v['key']]['expires']<=time.time() for v in edges[i]); flags=trial_reviews.get(i,[])+[reason for p in reviews[i] for reason in p['reasons']]
        status='proposed' if e else 'deferred' if unknown else 'review' if flags else 'unassigned'
        excluded=[reason for p in exclusions[i] for reason in p['reasons']]
        reason='Trajet IGN compatible vérifié (simulation)' if e else 'Trajets inconnus : poursuivre' if unknown else ' ; '.join(dict.fromkeys(flags if flags else excluded)) or 'Capacité, solde ou conflits entre propositions'
        r=routes[e['key']] if e else None
        rows.append(dict(n,row=i+2,status=status,reason=reason,teacher_id=e['teacher_id'] if e else '',duration_seconds=r['duration_seconds'] if r else None,route=r,partial=unknown,review_flags=list(dict.fromkeys(flags)) if status=='review' else [],exclusion_reasons=list(dict.fromkeys(excluded))))
    return rows

class BatchService:
    def __init__(self,store):
        self.store=store; self.lock=threading.Lock(); self.thread=None
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS batch_jobs(id TEXT PRIMARY KEY,status TEXT NOT NULL,body TEXT NOT NULL,generation INTEGER NOT NULL DEFAULT 0)''')
            db.execute("UPDATE batch_jobs SET status='interrupted',generation=generation+1 WHERE status='running'")
    def snapshot(self,db):
        business=self.store.business.read(db)
        teachers=effective_teachers(self.store.schools,self.store.teachers(db),business); assignments=self.store.assignments(db)
        fingerprint=context_fingerprint(self.store.schools,teachers,assignments,business)
        return fingerprint,teachers,assignments
    def load(self,db,j):
        if not isinstance(j,str) or len(j)!=32 or any(c not in '0123456789abcdef' for c in j): raise APIError(404,'Lot introuvable.')
        row=db.execute('SELECT * FROM batch_jobs WHERE id=?',(j,)).fetchone()
        if row is None: raise APIError(404,'Lot introuvable.')
        return row,json.loads(row['body'])
    def public(self,row,body):
        return dict(id=row['id'],status=row['status'],counts=counts(body['results']),results=body['results'],progress=body['progress'],snapshot=body['snapshot'],business_revision=body.get('business_revision'),partial=any(r['partial'] for r in body['results']),method='Heuristique configurée urgence/rareté/dates ; règles métier actuelles, capacité/RCD/séances vérifiées en contrôlé ; dates conservatrices en historique/EDT inconnu. Revue intersites et fuseaux non pris en charge. Propositions fictives uniquement, aucune affectation automatique.',updated_at=body.get('updated_at'))
    def create(self,payload):
        needs=validate_batch(payload,self.store.school_index); j=secrets.token_hex(16)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); fp,_,_=self.snapshot(db)
            body=dict(needs=needs,business_revision=self.store.business.read(db)['revision'],results=pending(needs),routes={},snapshot=fp,progress=dict(phase='queued',done=0,total=len(needs)),updated_at=time.time())
            db.execute('INSERT INTO batch_jobs(id,status,body) VALUES(?,?,?)',(j,'queued',encoded(body)))
        return self.get(j)
    def get(self,j):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); row,body=self.load(db,j); fp,_,_=self.snapshot(db)
            expired=any(r['expires']<=time.time() for r in body['routes'].values())
            if fp!=body['snapshot'] or expired:
                body['results']=pending(body['needs'],'Contexte ou trajets périmés : relancer pour revérifier'); body['routes']={}; body['snapshot']=fp; body['updated_at']=time.time()
                db.execute("UPDATE batch_jobs SET status='stale',body=?,generation=generation+1 WHERE id=?",(encoded(body),j))
                row,_=self.load(db,j)
            return self.public(row,body)
    def list(self):
        with self.store.connect() as db: ids=[r[0] for r in db.execute('SELECT id FROM batch_jobs ORDER BY rowid DESC LIMIT 100')]
        return [dict(id=r['id'],status=r['status'],counts=r['counts']) for r in map(self.get,ids)]
    def cancel(self,j):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); self.load(db,j)
            db.execute("UPDATE batch_jobs SET status='cancelled',generation=generation+1 WHERE id=?",(j,))
        return self.get(j)
    def run(self,j):
        with self.lock:
            if self.thread and self.thread.is_alive(): raise APIError(409,'Une passe serveur est déjà active ; patienter ou annuler.')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE'); row,body=self.load(db,j); fp,teachers,assignments=self.snapshot(db)
                if fp!=body['snapshot']: body['routes']={}
                body['business']=self.store.business.read(db); body['business_revision']=body['business']['revision']
                body.update(snapshot=fp,results=pending(body['needs'],'Revalidation du contexte en cours'),progress=dict(phase='eligibility',done=0,total=len(body['needs'])),updated_at=time.time())
                generation=row['generation']+1
                db.execute("UPDATE batch_jobs SET status='running',generation=?,body=? WHERE id=?",(generation,encoded(body),j))
            self.thread=threading.Thread(target=self._work,args=(j,generation,body,teachers,assignments),daemon=True,name='relai-batch')
            self.thread.start()
        return self.get(j)
    def wait(self):
        if self.thread: self.thread.join(timeout=45)
    def active(self,j,g):
        with self.store.connect() as db:
            row,_=self.load(db,j); return row['status']=='running' and row['generation']==g
    def save(self,j,g,body,status='running'):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); row,_=self.load(db,j)
            if row['status']!='running' or row['generation']!=g: return False
            fp,_,_=self.snapshot(db)
            if fp!=body['snapshot']:
                body.update(results=pending(body['needs'],'Contexte modifié pendant la passe : relancer'),routes={},snapshot=fp)
                status='stale'
            body['updated_at']=time.time()
            db.execute('UPDATE batch_jobs SET status=?,body=? WHERE id=?',(status,encoded(body),j))
            return status!='stale'
    def _work(self,j,g,body,teachers,assignments):
        try:
            needs=body['needs']; bysubject={}
            for t in teachers:
                for subject in t['subjects']: bysubject.setdefault(subject,[]).append(t)
            edges=[]; reviews=[]; exclusions=[]; business=body['business']
            for i,n in enumerate(needs):
                if i%25==0:
                    if not self.active(j,g): return
                    body['progress'].update(done=i)
                    if not self.save(j,g,body): return
                school=self.store.school_index[n['school_id']]
                matching=match_candidates(n,school,bysubject.get(n['subject'],[]),assignments,n['max_distance_km'],business)
                reviews.append(matching['review']); exclusions.append(matching['excluded']); candidates=matching['candidates']
                edges.append([dict(teacher_id=c['teacher']['id'],capacity=c['teacher']['capacity_hours'],key=encoded([[c['teacher']['lon'],c['teacher']['lat']],[school['lon'],school['lat']]])) for c in candidates])
            # Round-robin across needs, global 80 endpoint pairs, one RouteService
            # invocation (<=30 s, <=4 workers, <=4 rps; no automatic retry loops).
            now=time.time(); routes={k:v for k,v in body['routes'].items() if v['expires']>now}; unknown=[]; seen=set()
            for depth in range(max((len(e) for e in edges),default=0)):
                for es in edges:
                    if depth<len(es):
                        key=es[depth]['key']
                        if key not in routes and key not in seen: unknown.append(key); seen.add(key)
            offset=body.get('route_offset',0)%len(unknown) if unknown else 0
            targets=(unknown[offset:]+unknown[:offset])[:80]
            body['route_offset']=(offset+len(targets))%len(unknown) if unknown else 0
            body['progress']=dict(phase='routing',done=len(needs),total=len(needs),route_targets=len(targets))
            if not self.save(j,g,body): return
            response=self.store.router.route_many([json.loads(k) for k in targets]) if targets else []
            if len(response)!=len(targets): raise ValueError('Réponse de routage incomplète')
            for key,r in zip(targets,response):
                if r.get('status') not in ('ok','no_route'): continue
                evidence={k:v for k,v in r.items() if k!='geometry'}
                evidence['expires']=time.time()+(604800 if r['status']=='ok' else 3600)
                routes[key]=evidence
            body['routes']=routes; body['results']=self.plan(needs,edges,routes,business,teachers,assignments,self.store.school_index,reviews,exclusions)
            body['business_revision']=business['revision']
            for n,r in zip(needs,body['results']):
                school=self.store.school_index[n['school_id']]
                if school.get('lat') is None or school.get('lon') is None or school.get('sector') not in ('Public','Privé'):
                    r.update(status='deferred',partial=True,reason='Coordonnées ou secteur inconnus : compatibilité non vérifiable')
            body['progress'].update(phase='finished',route_results=len(response))
            self.save(j,g,body,'partial' if any(r['partial'] for r in body['results']) else 'completed')
        except Exception:
            body['progress']['phase']='error'
            body['results']=pending(body['needs'],'Erreur de calcul : relancer, aucune affectation effectuée')
            self.save(j,g,body,'failed')
    @staticmethod
    def plan(needs,edges,routes,business=None,teachers=(),assignments=(),schools=None,reviews=(),exclusions=()):
        if business and business['config']['mode']=='controlled':
            return controlled_plan(needs,edges,routes,business,teachers,assignments,schools,reviews,exclusions)
        usable=[]; unknown=[]
        for n,es in zip(needs,edges):
            unknown.append(any(e['key'] not in routes for e in es))
            candidates=[e for e in es if e['key'] in routes and routes[e['key']]['status']=='ok' and routes[e['key']]['duration_seconds']<=n['max_travel_minutes']*60]
            candidates.sort(key=lambda e:(routes[e['key']]['duration_seconds'],routes[e['key']]['road_distance_km'],-e['capacity'],e['teacher_id']))
            usable.append(candidates)
        order=sorted(range(len(needs)),key=lambda i:(needs[i]['urgency']!='Urgente',len(edges[i]),needs[i]['start_date'],i))
        occupied={}; chosen={}
        for i in order:
            n=needs[i]
            for e in usable[i]:
                if any(a['start_date']<=n['end_date'] and a['end_date']>=n['start_date'] for a in occupied.get(e['teacher_id'],[])): continue
                chosen[i]=e; occupied.setdefault(e['teacher_id'],[]).append(n); break
        rows=[]
        for i,n in enumerate(needs):
            e=chosen.get(i); status='proposed' if e else 'deferred' if unknown[i] else 'unassigned'
            r=routes[e['key']] if e else None
            rows.append(dict(n,row=i+2,status=status,teacher_id=e['teacher_id'] if e else '',duration_seconds=r['duration_seconds'] if r else None,route=r,partial=unknown[i],reason='Trajet IGN compatible ; comparaison partielle' if e and unknown[i] else 'Trajet IGN compatible vérifié' if e else 'Trajets inconnus : poursuivre' if unknown[i] else 'Aucun profil ou trajet compatible, ou conflit de dates'))
        return rows
