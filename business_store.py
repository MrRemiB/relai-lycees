"""Transactional full-replace anonymous business documents and audit events."""
import datetime as dt
import hashlib
import json
import re
from urllib.parse import parse_qs
from business import default_business, validate_business, revision, timestamp, MAX_BYTES


def encoded(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

class BusinessStore:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS business_config(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS business_events(id INTEGER PRIMARY KEY AUTOINCREMENT,revision INTEGER NOT NULL,actor TEXT NOT NULL,kind TEXT NOT NULL,observed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS business_idempotency(actor TEXT NOT NULL,key TEXT NOT NULL,digest TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(actor,key));''')
            db.execute('INSERT OR IGNORE INTO business_config VALUES(1,?)',(encoded(default_business()),))
    def read(self,db): return json.loads(db.execute('SELECT body FROM business_config WHERE id=1').fetchone()[0])
    def event(self,db,actor,kind):
        observed=dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        db.execute('INSERT INTO business_events(revision,actor,kind,observed_at) VALUES(?,?,?,?)',(self.read(db)['revision'],actor,kind,observed))

    def invalidate(self,db):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='batch_jobs'").fetchone(): return
        for row in db.execute('SELECT id,body FROM batch_jobs').fetchall():
            body=json.loads(row['body']); body['routes']={}
            body['results']=[dict(n,row=i+2,status='deferred',reason='Configuration/profils modifiés : recalcul requis',teacher_id='',duration_seconds=None,route=None,partial=True) for i,n in enumerate(body['needs'])]
            db.execute("UPDATE batch_jobs SET status='stale',generation=generation+1,body=? WHERE id=?",(encoded(body),row['id']))
    def dispatch(self,method,path,payload,actor='coordinator',query=''):
        from app import APIError,decode_json
        with self.store.connect() as db:
            if method=='GET':
                db.execute('BEGIN'); b=self.read(db)
                if path in ('/api/business','/api/v1/config'): return 200,b
                if path.startswith('/api/v1/reference/'):
                    key=path.rsplit('/',1)[1]
                    if key not in ('zones','profiles','timetables'): raise APIError(404,'Référentiel introuvable.')
                    items=b[key] if key!='timetables' else [dict(teacher_id=p['teacher_id'],timetable=p['timetable']) for p in b['profiles']]
                    return 200,dict(schema_version=1,revision=b['revision'],items=items)
                if path=='/api/v1/events':
                    q=parse_qs(query,keep_blank_values=True,strict_parsing=True)
                    if set(q)-{'cursor','limit'} or any(len(v)!=1 for v in q.values()): raise ValueError('Pagination invalide.')
                    cursor=q.get('cursor',['v1:0'])[0]; limit=q.get('limit',['100'])[0]
                    if not re.fullmatch(r'v1:(0|[1-9][0-9]{0,18})',cursor) or not re.fullmatch('[1-9][0-9]{0,2}',limit) or int(limit)>200: raise ValueError('Curseur v1 et limite 1..200 requis.')
                    after=int(cursor[3:])
                    if after>9223372036854775807: raise ValueError('Curseur hors plage.')
                    rows=[dict(r) for r in db.execute('SELECT * FROM business_events WHERE id>? ORDER BY id LIMIT ?',(after,int(limit)+1))]
                    more=len(rows)>int(limit); rows=rows[:int(limit)]
                    return 200,dict(schema_version=1,revision=b['revision'],events=rows,next_cursor='v1:'+str(rows[-1]['id'] if rows else after),has_more=more)
            reset=path=='/api/business/reset' and method=='POST'
            commit=(path in ('/api/business/commit','/api/v1/imports/commit') and method=='POST') or (path=='/api/v1/config' and method=='PUT')
            validate=path in ('/api/business/validate','/api/v1/imports/validate') and method=='POST'
            if not (reset or commit or validate): raise APIError(404,'Ressource introuvable.')
            db.execute('BEGIN IMMEDIATE' if commit or reset else 'BEGIN'); current=self.read(db)
            digest=None
            if reset:
                if payload!={'confirm':True}: raise ValueError('Confirmation requise.')
                b=default_business(); expected=current['revision']
            else:
                required={'document','expected_revision','confirm_demo'}
                allowed=required|{'observed_at','source_reference'}|({'idempotency_key'} if commit else set())
                if not isinstance(payload,dict) or not required<=set(payload) or set(payload)-allowed or payload['confirm_demo'] is not True: raise ValueError('Document fictif strict et confirmation requis.')
                expected=revision(payload['expected_revision']); key=payload.get('idempotency_key')
                if path.startswith('/api/v1/') and commit and key is None: raise ValueError('Idempotency key requise.')
                if key is not None and (not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9_-]{8,128}',key)): raise ValueError('Idempotency key invalide.')
                digest=hashlib.sha256(encoded(payload).encode()).hexdigest()
                if commit and key:
                    cached=db.execute('SELECT digest,result FROM business_idempotency WHERE actor=? AND key=?',(actor,key)).fetchone()
                    if cached:
                        if cached['digest']!=digest: raise APIError(409,'Idempotency key réutilisée avec un autre payload.')
                        return 200,json.loads(cached['result'])
                if expected!=current['revision']: raise APIError(409,'Révision métier obsolète.')
                if 'observed_at' in payload and timestamp(payload['observed_at'])>dt.datetime.now(dt.timezone.utc).timestamp(): raise ValueError('Observation future interdite.')
                if 'source_reference' in payload:
                    from business import text
                    text(payload['source_reference'],300)
                raw_document=payload['document']
                if len((raw_document if isinstance(raw_document,str) else encoded(raw_document)).encode())>MAX_BYTES: raise APIError(413,'Document métier limité à 2,5 Mo UTF8.')
                document=decode_json(raw_document) if isinstance(raw_document,str) else raw_document
                b=validate_business(document,self.store.schools,self.store.teachers(db))
                # Source stamps are authoritative data, never overridden by envelope observation time.
            if validate: return 200,dict(valid=True,document=b,revision=current['revision'])
            b['revision']=revision(expected+1)
            db.execute('UPDATE business_config SET body=? WHERE id=1',(encoded(b),)); self.invalidate(db)
            self.event(db,actor,'reset' if reset else 'business.replace')
            if not reset and payload.get('idempotency_key'):
                db.execute('INSERT INTO business_idempotency VALUES(?,?,?,?)',(actor,payload['idempotency_key'],digest,encoded(b)))
            return 200,self.read(db)
