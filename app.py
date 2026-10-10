"""Local anonymous simulation API. No production HR data or authentication."""
import argparse
from contextlib import contextmanager
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit, unquote

from matching import SUBJECTS, PATHWAYS, boolean, coordinates, date, match_candidates, match_routed_candidates, need_identifier, number, validate_need
from routing import RouteService, METADATA as ROUTING_METADATA
from scripts.generate_demo import generate_teachers
from business import effective_teachers, context_fingerprint, revision
from business_store import BusinessStore

ROOT=Path(__file__).resolve().parent
MAX_BODY=1048576

class APIError(Exception):
    def __init__(self,status,message): self.status,self.message=status,message


def decode_json(raw):
    def constant(value): raise ValueError('Nombre JSON non fini interdit.')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ValueError('Clé JSON dupliquée.')
            result[k]=v
        return result
    return json.loads(raw,parse_constant=constant,object_pairs_hook=pairs)


class Store:
    def __init__(self, db_path, school_data, teachers, calendar_data, router=None):
        self.path=str(db_path)
        Path(db_path).parent.mkdir(parents=True,exist_ok=True)
        self.schools=school_data['schools']
        self.school_index={s['id']:s for s in self.schools}
        self.metadata=school_data.get('metadata',{})
        self.calendar=calendar_data
        self.router=router if router is not None else RouteService(Path(db_path).parent/'routes.sqlite3')
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS teachers(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS needs(id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY AUTOINCREMENT, need_id INTEGER NOT NULL UNIQUE REFERENCES needs(id), teacher_id TEXT NOT NULL REFERENCES teachers(id), start_date TEXT NOT NULL, end_date TEXT NOT NULL, hours REAL NOT NULL, created_at TEXT NOT NULL);
            ''')
            if 'route' not in {r[1] for r in db.execute('PRAGMA table_info(assignments)')}:
                db.execute('ALTER TABLE assignments ADD COLUMN route TEXT')
            if not db.execute('SELECT 1 FROM teachers LIMIT 1').fetchone():
                initial=teachers if teachers is not None else generate_teachers(self.schools)
                db.executemany('INSERT INTO teachers VALUES (?,?)',[(t['id'],json.dumps(t,ensure_ascii=False,allow_nan=False)) for t in initial])

        self.business=BusinessStore(self)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def teachers(self,db): return [json.loads(r['body']) for r in db.execute('SELECT body FROM teachers ORDER BY id')]
    def needs(self,db): return [json.loads(r['body']) for r in db.execute('SELECT body FROM needs ORDER BY id DESC')]
    def assignments(self,db):
        rows=[dict(r) for r in db.execute('SELECT * FROM assignments ORDER BY id')]
        needs={n['id']:n for n in self.needs(db)}
        for r in rows:
            if r.get('route'): r['route']=json.loads(r['route'])
            n=needs.get(r['need_id'],{})
            for k in ('school_id','mission_type','sessions'):
                if k in n: r[k]=n[k]
            if (r.get('route') or {}).get('route_origin_school_id'): r['route_origin_school_id']=r['route']['route_origin_school_id']
        return rows
    def need(self,db,identifier):
        need_identifier(identifier)
        row=db.execute('SELECT body FROM needs WHERE id=?',(identifier,)).fetchone()
        if row is None: raise APIError(404,'Besoin introuvable.')
        return json.loads(row['body'])
    def save(self,db,n): db.execute('UPDATE needs SET body=? WHERE id=?',(json.dumps(n,ensure_ascii=False,allow_nan=False),n['id']))

    def dispatch(self,method,path,payload,actor='coordinator',query=''):
        if path.startswith('/api/business') or path.startswith('/api/v1/'):
            return self.business.dispatch(method,path,payload,actor,query)
        with self.connect() as db:
            if method=='GET':
                if path=='/api/calendar': return 200,self.calendar
                if path=='/api/needs': return 200,{'needs':self.needs(db)}
                if path=='/api/bootstrap':
                    db.execute('BEGIN')
                    business=self.business.read(db)
                    ts=effective_teachers(self.schools,self.teachers(db),business)
                    return 200,dict(business=business,schools=self.schools,teachers=ts,needs=self.needs(db),assignments=self.assignments(db),metadata=dict(self.metadata,teacher_count=len(ts),demo=True,subjects=SUBJECTS,pathways=PATHWAYS,today=dt.date.today().isoformat(),calendar=self.calendar.get('metadata',{}),routing=ROUTING_METADATA))
            elif method=='POST':
                if path=='/api/needs':
                    n=validate_need(payload,self.school_index,creation=True)
                    db.execute('BEGIN IMMEDIATE')
                    identifier=db.execute('INSERT INTO needs(body) VALUES (?)',('{}',)).lastrowid
                    n.update(id=identifier,status='open',teacher_id=None,created_at=dt.datetime.now(dt.timezone.utc).isoformat())
                    self.save(db,n)
                    return 201,{'need':n}
                if path=='/api/match':
                    n=validate_need(payload,self.school_index)
                    db.execute('BEGIN')
                    if 'need_id' in n:
                        stored=self.need(db,n['need_id'])
                        for key in ['school_id','subject','pathway','start_date','end_date','hours','allow_cross_academy','mission_type','sessions']:
                            fallback='unknown' if key=='mission_type' else None
                            if n.get(key,fallback)!=stored.get(key,fallback): raise ValueError('Le scénario doit correspondre au besoin enregistré.')
                        if n['max_travel_minutes']!=stored.get('max_travel_minutes',90): raise ValueError('Le trajet maximum doit correspondre au besoin enregistré.')
                    business=self.business.read(db)
                    teachers,assignments=effective_teachers(self.schools,self.teachers(db),business),self.assignments(db)
                    snapshot=context_fingerprint(self.schools,teachers,assignments,business)
                    db.commit()
                    result=match_routed_candidates(n,self.school_index[n['school_id']],teachers,assignments,self.router,n.get('max_distance_km',150),business)
                    db.execute('BEGIN')
                    current=self.business.read(db)
                    if snapshot!=context_fingerprint(self.schools,effective_teachers(self.schools,self.teachers(db),current),self.assignments(db),current): raise APIError(409,'Contexte modifié pendant le calcul.')
                    result.update(business_revision=business['revision'],business_mode=business['config']['mode'],snapshot=snapshot)
                    return 200,result
                if path=='/api/teachers/import': return self.import_teachers(db,payload,actor)
                found=re.fullmatch(r'/api/needs/([1-9][0-9]*)/(assign|release|close)',path)
                if found:
                    identifier,action=need_identifier(int(found[1])),found[2]
                    allowed={'teacher_id','max_distance_km','max_travel_minutes','business_revision'} if action=='assign' else set()
                    if set(payload)-allowed: raise ValueError('Champs inconnus.')
                    if action=='assign':
                        if not isinstance(payload.get('teacher_id'),str): raise ValueError('Identifiant de profil requis.')
                        number(payload.get('max_distance_km',150),'Rayon',0,2000)
                        if 'max_travel_minutes' in payload: number(payload['max_travel_minutes'],'Trajet maximum',0,480)
                        # No routing/network while holding the SQLite write transaction.
                        db.execute('BEGIN')
                        business=self.business.read(db)
                        if 'business_revision' in payload and revision(payload['business_revision'])!=business['revision']: raise APIError(409,'Révision métier obsolète.')
                        before=self.need(db,identifier)
                        if before['status']!='open': raise APIError(409,'Le besoin n’est plus ouvert.')
                        if payload.get('max_travel_minutes',before.get('max_travel_minutes',90))!=before.get('max_travel_minutes',90): raise ValueError('Le trajet maximum doit correspondre au besoin enregistré.')
                        effective=effective_teachers(self.schools,self.teachers(db),business)
                        assignments=self.assignments(db)
                        snapshot=context_fingerprint(self.schools,effective,assignments,business)
                        selected=[t for t in effective if t['id']==payload['teacher_id']]
                        if not selected: raise APIError(404,'Profil introuvable.')
                        db.commit()
                        result=match_routed_candidates(before,self.school_index[before['school_id']],selected,assignments,self.router,payload.get('max_distance_km',150),business)
                        if not result['candidates']: raise APIError(409,'Profil incompatible, itinéraire indisponible ou trajet supérieur au maximum.')
                        candidate=result['candidates'][0]
                        audit={k:candidate[k] for k in ('duration_seconds','road_distance_km')}
                        audit.update({k:candidate['route'][k] for k in ('provider','resource_version','computed_at')})
                        if business['config']['mode']=='controlled': audit['route_origin_school_id']=next(p['rad_school_id'] for p in business['profiles'] if p['teacher_id']==payload['teacher_id'])
                    db.execute('BEGIN IMMEDIATE')
                    n=self.need(db,identifier)
                    if action=='assign':
                        if n['status']!='open': raise APIError(409,'Le besoin n’est plus ouvert.')
                        if n!=before: raise APIError(409,'Besoin modifié pendant le calcul. Actualisez les candidatures.')
                        current_business=self.business.read(db)
                        teachers=effective_teachers(self.schools,self.teachers(db),current_business)
                        if snapshot!=context_fingerprint(self.schools,teachers,self.assignments(db),current_business): raise APIError(409,'Configuration ou état modifié pendant le routage.')
                        if not any(t['id']==payload['teacher_id'] for t in teachers): raise APIError(404,'Profil introuvable.')
                        result=match_candidates(n,self.school_index[n['school_id']],teachers,self.assignments(db),payload.get('max_distance_km',150),current_business)
                        if not any(c['teacher']['id']==payload['teacher_id'] for c in result['candidates']): raise APIError(409,'Profil désormais incompatible ou période déjà affectée. Actualisez les candidatures.')
                        created=dt.datetime.now(dt.timezone.utc).isoformat()
                        # Recheck the selected anchor as well as every hard/date constraint.
                        current=next(t for t in teachers if t['id']==payload['teacher_id'])
                        if current!=selected[0]: raise APIError(409,'Profil modifié pendant le calcul.')
                        aid=db.execute('INSERT INTO assignments(need_id,teacher_id,start_date,end_date,hours,created_at,route) VALUES (?,?,?,?,?,?,?)',(identifier,payload['teacher_id'],n['start_date'],n['end_date'],n['hours'],created,json.dumps(audit,allow_nan=False))).lastrowid
                        n.update(status='assigned',teacher_id=payload['teacher_id'])
                        self.save(db,n)
                        assignment=dict(id=aid,need_id=identifier,teacher_id=n['teacher_id'],start_date=n['start_date'],end_date=n['end_date'],hours=n['hours'],created_at=created,route=audit)
                        assignment.update({k:n[k] for k in ('school_id','mission_type','sessions') if k in n})
                        return 200,dict(need=n,assignment=assignment)
                    if action=='release':
                        if n['status']!='assigned': raise APIError(409,'Seul un besoin affecté peut être libéré.')
                        db.execute('DELETE FROM assignments WHERE need_id=?',(identifier,))
                        n.update(status='open',teacher_id=None)
                    else:
                        if n['status']!='open': raise APIError(409,'Libérez d’abord toute affectation ; seul un besoin ouvert peut être clos.')
                        n['status']='closed'
                    self.save(db,n)
                    return 200,{'need':n}
            raise APIError(404,'Ressource introuvable.')

    def import_teachers(self,db,payload,actor='coordinator'):
        if set(payload)!={'teachers','confirm_demo'} or payload.get('confirm_demo') is not True:
            raise ValueError('Import exclusivement démo : confirm_demo:true requis.')
        batch=payload['teachers']
        if not isinstance(batch,list) or not 1<=len(batch)<=200: raise ValueError('Lot de 1 à 200 profils démo requis.')
        fields={'id','name','subjects','academy','sector','lat','lon','base_label','capacity_hours','max_distance_km','available_from','available_until','pathways','cross_academy'}
        academies={s['academy'] for s in self.schools}
        ids=set()
        for t in batch:
            if not isinstance(t,dict) or set(t)!=fields: raise ValueError('Schéma de profil démo strict requis, aucun champ personnel.')
            if not isinstance(t['id'],str) or not re.fullmatch(r'DEMO-[0-9]{4,8}',t['id']): raise ValueError('Identifiant DEMO-0000 requis.')
            digits=t['id'][5:]
            if t['name']!='Profil démo '+digits: raise ValueError('Nom anonyme Profil démo suivi du numéro requis.')
            if t['id'] in ids: raise ValueError('Identifiant dupliqué dans le lot.')
            ids.add(t['id'])
            if t['academy'] not in academies or t['sector'] not in ['Public','Privé']: raise ValueError('Académie ou secteur inconnu.')
            for key,options in [('subjects',SUBJECTS),('pathways',PATHWAYS)]:
                if not isinstance(t[key],list) or not t[key] or any(not isinstance(v,str) or v not in options for v in t[key]) or len(set(t[key]))!=len(t[key]): raise ValueError('Discipline ou voie invalide.')
            if not coordinates(t['lat'],t['lon']): raise ValueError('Coordonnées requises.')
            # Imported anchors must be an official school location, never arbitrary home GPS.
            anchors=[s for s in self.schools if s['academy']==t['academy'] and s['sector']==t['sector'] and s.get('lat')==t['lat'] and s.get('lon')==t['lon']]
            if not anchors: raise ValueError('Ancrage officiel d’établissement requis.')
            if not isinstance(t['base_label'],str) or not 1<=len(t['base_label'])<=300: raise ValueError('Libellé démo requis.')
            # Ignore arbitrary text to prevent personal data being carried by this field.
            anchor=anchors[0]
            t['base_label']=f"Ancrage administratif fictif · {anchor['name']} · {anchor['city']}"
            number(t['capacity_hours'],'Capacité',0.1,60)
            number(t['max_distance_km'],'Mobilité',0,2000)
            boolean(t['cross_academy'],'cross_academy')
            if date(t['available_from'])>date(t['available_until']): raise ValueError('Disponibilité invalide.')
        db.execute('BEGIN IMMEDIATE')
        existing={r[0] for r in db.execute('SELECT id FROM teachers')}
        if ids & existing: raise APIError(409,'Un identifiant existe déjà ; import append-only.')
        if len(existing)+len(batch)>5000: raise ValueError('Limite de 5000 profils démo.')
        db.executemany('INSERT INTO teachers VALUES (?,?)',[(t['id'],json.dumps(t,ensure_ascii=False,allow_nan=False)) for t in batch])
        self.business.invalidate(db); self.business.event(db,actor,'roster.append')
        return 200,{'imported':len(batch)}


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args): pass
    def json_response(self,status,body):
        data=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def handle_request(self):
        self.connection.settimeout(10)
        try:
            parsed=urlsplit(self.path)
            path=unquote(parsed.path)
            if path.startswith('/api/'):
                payload=None
                if self.command=='POST':
                    if self.headers.get('Transfer-Encoding'): raise APIError(400,'Encodage de transfert non pris en charge.')
                    if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json': raise APIError(415,'Content-Type application/json requis.')
                    lengths=self.headers.get_all('Content-Length',[])
                    if len(lengths)!=1 or not re.fullmatch(r'[0-9]+',lengths[0]): raise APIError(400,'Content-Length valide requis.')
                    length=int(lengths[0])
                    if length>MAX_BODY: raise APIError(413,'Corps JSON limité à 1 Mio.')
                    raw=self.rfile.read(length)
                    if len(raw)!=length: raise ValueError('Corps JSON incomplet.')
                    payload=decode_json(raw)
                    if not isinstance(payload,dict): raise ValueError('Objet JSON requis.')
                status,body=self.server.store.dispatch(self.command,path,payload)
                self.json_response(status,body)
            elif self.command=='GET': self.static_response(path)
            else: raise APIError(404,'Ressource introuvable.')
        except APIError as e: self.json_response(e.status,{'error':e.message})
        except (ValueError,TypeError,KeyError,UnicodeError,RecursionError): self.json_response(400,{'error':'Données invalides : vérifiez les champs, dates, booléens et nombres finis.'})
        except sqlite3.OperationalError: self.json_response(503,{'error':'Stockage momentanément indisponible.'})
        except TimeoutError: self.json_response(408,{'error':'Délai de requête dépassé.'})

    def static_response(self,path):
        root=self.server.static_dir
        relative='index.html' if path=='/' else path.removeprefix('/static/') if path.startswith('/static/') else None
        if relative is None or not relative or any(p in ('.','..') for p in relative.split('/')) or '\\' in relative: raise APIError(404,'Ressource introuvable.')
        target=(root/relative).resolve()
        if not target.is_relative_to(root) or target.suffix.lower() not in {'.html','.css','.js','.json','.svg','.png','.jpg','.jpeg','.webp','.ico','.woff','.woff2'} or not target.is_file(): raise APIError(404,'Ressource introuvable.')
        data=target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',(mimetypes.guess_type(target)[0] or 'application/octet-stream')+('; charset=utf-8' if target.suffix in ['.html','.css','.js','.json','.svg'] else ''))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers(); self.wfile.write(data)

    do_GET=handle_request
    do_POST=handle_request


def create_server(host='127.0.0.1',port=8127,*,db_path=None,school_data=None,teachers=None,static_dir=None,calendar_data=None,router=None):
    if host!='127.0.0.1': raise ValueError('Service démo réservé à 127.0.0.1.')
    if school_data is None: school_data=decode_json((ROOT/'data/schools.json').read_bytes())
    if calendar_data is None:
        calendar_path=ROOT/'data/calendar.json'
        calendar_data=decode_json(calendar_path.read_bytes()) if calendar_path.exists() else {'metadata':{'available':False},'holidays':[]}
    store=Store(db_path or ROOT/'runtime/relai.sqlite3',school_data,teachers,calendar_data,router=router)
    server=ThreadingHTTPServer((host,port),Handler)
    server.daemon_threads=True
    server.store=store
    server.static_dir=Path(static_dir or ROOT/'static').resolve()
    return server


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=int(os.environ.get('RELAI_PORT','8127')))
    args=parser.parse_args()
    server=create_server(port=args.port)
    print(f'Relai Lycées démo http://127.0.0.1:{server.server_port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
