"""Browser business-core v1 parity. Local fictitious rules, not national law."""
import copy
import datetime as dt
import hashlib
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from matching import date, number, boolean

MAX_BYTES=2_500_000
SAFE=9007199254740991

def strict(o,keys):
    if not isinstance(o,dict) or set(o)!=set(keys): raise ValueError('Objet strict : champs manquants/inconnus, aucune donnée RH personnelle.')
def choice(v,values):
    if v not in values: raise ValueError('Valeur inconnue.')
def text(v,maximum=160):
    if not isinstance(v,str) or not v.strip() or len(v.encode('utf-16-le'))//2>maximum or re.search(r'[\x00-\x1f]',v): raise ValueError('Libellé borné requis.')
def revision(v):
    if type(v) not in (int,float) or not 0<=v<=SAFE or int(v)!=v: raise ValueError('Révision entière sûre requise.')
    return int(v)

def timestamp(v):
    if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z',v): raise ValueError('Horodatage UTC requis.')
    date(v[:10]); return dt.datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
def listing(v,check,maximum=5000):
    if not isinstance(v,list) or len(v)>maximum or len({json.dumps(x,sort_keys=True) for x in v})!=len(v): raise ValueError('Liste bornée sans doublons requise.')
    for x in v: check(x)
def interval(o):
    if date(o['start_date'])>date(o['end_date']): raise ValueError('Intervalle inversé.')
def default_business():
    return dict(schema_version=1,revision=0,config=dict(mode='historical',label='Démo simple historique — non contrôle métier',academy=None,school_ids=[],source_reference=None,validated_on=None,state='draft',mission_modes=['RCD','rectoral'],rcd_max_days=14,freshness_days=30,travel_margin_minutes=10,out_of_zone='exclude',mobility_mode='car',priority='urgent_scarcity'),zones=[],profiles=[])
def validate_sessions(sessions,schools,need=None):
    ids={s['id'] for s in schools}
    def check(s):
        strict(s,['date','start','end','timezone','school_id']); date(s['date'])
        for k in ('start','end'):
            if not isinstance(s[k],str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',s[k]): raise ValueError('Horaire HH:MM requis.')
        if s['start']>=s['end']: raise ValueError('Séance inversée.')
        if not isinstance(s['timezone'],str) or len(s['timezone'])>80: raise ValueError('Fuseau IANA requis.')
        try: ZoneInfo(s['timezone'])
        except (ZoneInfoNotFoundError,ValueError): raise ValueError('Fuseau inconnu.') from None
        if s['school_id'] not in ids: raise ValueError('Site inconnu.')
        if need and not need['start_date']<=s['date']<=need['end_date']: raise ValueError('Séance hors dates.')
    listing(sessions,check,1000)
    for i,a in enumerate(sessions):
        for b in sessions[:i]:
            if a['date']==b['date'] and a['timezone']==b['timezone'] and a['start']<b['end'] and b['start']<a['end']: raise ValueError('Séances chevauchantes.')
    return sessions

def validate_business(b,schools,teachers):
    strict(b,['schema_version','revision','config','zones','profiles'])
    if type(b['schema_version']) not in (int,float) or b['schema_version']!=1: raise ValueError('Version inconnue.')
    revision(b['revision']); c=b['config']; strict(c,default_business()['config'])
    academies={s['academy'] for s in schools}; sites={s['id']:s for s in schools}; tids={t['id'] for t in teachers}
    def site(v):
        if not isinstance(v,str) or not re.fullmatch(r'\d{7}[A-Z]',v) or v not in sites: raise ValueError('UAI inexistant.')
    choice(c['mode'],['historical','controlled']); text(c['label'])
    if c['academy'] is not None: choice(c['academy'],academies)
    listing(c['school_ids'],site)
    if c['source_reference'] is not None: text(c['source_reference'],300)
    if c['validated_on'] is not None: date(c['validated_on'])
    choice(c['state'],['draft','validated']); listing(c['mission_modes'],lambda v:choice(v,['RCD','rectoral']),2)
    if not c['mission_modes']: raise ValueError('Circuit requis.')
    for k,lo,hi in [('rcd_max_days',1,365),('freshness_days',1,3650),('travel_margin_minutes',0,240)]: number(c[k],k,lo,hi)
    for k,vs in [('out_of_zone',['exclude','review']),('mobility_mode',['car','manual']),('priority',['urgent_scarcity','scarcity'])]: choice(c[k],vs)
    zids=set()
    def zonecheck(z):
        strict(z,['id','label','academy','school_ids','adjacent_zone_ids'])
        if not isinstance(z['id'],str) or not re.fullmatch(r'Z[A-Za-z0-9_-]{1,63}',z['id']) or z['id'] in zids: raise ValueError('ID zone unique requis.')
        zids.add(z['id']); text(z['label']); choice(z['academy'],academies)
        def zs(v):
            site(v)
            if sites[v]['academy']!=z['academy']: raise ValueError('UAI hors académie.')
        listing(z['school_ids'],zs)
    listing(b['zones'],zonecheck,500)
    def zone(v):
        if not isinstance(v,str) or v not in zids: raise ValueError('Zone inconnue.')
    for z in b['zones']:
        listing(z['adjacent_zone_ids'],zone,500)
        if z['id'] in z['adjacent_zone_ids']: raise ValueError('Auto-adjacence interdite.')
    seen=set()
    def profile(p):
        strict(p,['teacher_id','status','rad_school_id','zone_ids','contract','capacity_hours','capacity_validated','rcd_engagement','mobility_modes','cross_academy','source_updated_at','availability','timetable'])
        tid=p['teacher_id']
        if not isinstance(tid,str) or not re.fullmatch(r'DEMO-\d{4,8}',tid) or tid not in tids or tid in seen: raise ValueError('Profil DEMO existant unique requis.')
        seen.add(tid); choice(p['status'],['TZR','contractual','RCD','unknown'])
        if p['rad_school_id'] is not None: site(p['rad_school_id'])
        listing(p['zone_ids'],zone,500)
        if p['capacity_hours'] is not None: number(p['capacity_hours'],'Capacité',.1,60)
        boolean(p['capacity_validated'],'capacité'); boolean(p['cross_academy'],'cross_academy'); listing(p['mobility_modes'],lambda v:choice(v,['car','manual']),2)
        if p['source_updated_at'] is not None: timestamp(p['source_updated_at'])
        k=p['contract']
        if k is not None:
            strict(k,['start_date','end_date','school_ids','zone_ids','validated']); interval(k); listing(k['school_ids'],site); listing(k['zone_ids'],zone); boolean(k['validated'],'contrat')
        e=p['rcd_engagement']
        if e is not None:
            strict(e,['school_id','start_date','end_date','hours_limit','hours_reserved','hours_done','validated']); site(e['school_id']); interval(e)
            for k in ['hours_limit','hours_reserved','hours_done']: number(e[k],k,0,2000)
            boolean(e['validated'],'engagement')
        if p['availability'] is not None: strict(p['availability'],['start_date','end_date']); interval(p['availability'])
        tt=p['timetable']
        if tt is not None:
            strict(tt,['known','sessions','source_updated_at']); boolean(tt['known'],'known'); validate_sessions(tt['sessions'],schools)
            if tt['source_updated_at'] is not None: timestamp(tt['source_updated_at'])
    listing(b['profiles'],profile)
    if len(json.dumps(b,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())>MAX_BYTES: raise ValueError('Métier limité à 2,5 Mo.')
    return copy.deepcopy(b)

def minutes(v): return int(v[:2])*60+int(v[3:])
def session_hours(sessions): return sum((minutes(s['end'])-minutes(s['start']))/60 for s in sessions or [])
def overlap(a,b): return a['start_date']<=b['end_date'] and a['end_date']>=b['start_date']
def local_rcd_hours(assignments,tid,e): return sum(session_hours(a.get('sessions')) for a in assignments if a['teacher_id']==tid and a.get('mission_type')=='RCD' and a.get('school_id')==e['school_id'] and overlap(a,e))
def clock_review(sessions):
    zone=ZoneInfo('Europe/Paris')
    for s in sessions or []:
        if s['timezone']!='Europe/Paris': return 'Fuseau hors Europe/Paris : revue manuelle, aucune conversion supposée'
        values=[]
        for k in ['start','end']:
            wall=dt.datetime.fromisoformat(s['date']+'T'+s[k]); candidates=set()
            for fold in [0,1]:
                aware=wall.replace(tzinfo=zone,fold=fold); utc=aware.astimezone(dt.timezone.utc)
                if utc.astimezone(zone).replace(tzinfo=None)==wall: candidates.add(utc.timestamp())
            values.append(candidates)
        if any(len(v)!=1 for v in values) or next(iter(values[1]))-next(iter(values[0]))!=(minutes(s['end'])-minutes(s['start']))*60: return 'Heure Europe/Paris inexistante, ambiguë ou changement de décalage : revue manuelle'
    return None

def result(ex,rv):
    ex=list(dict.fromkeys(ex)); rv=list(dict.fromkeys(rv))
    return dict(status='excluded' if ex else 'review' if rv else 'eligible',reasons=ex+rv,review_flags=rv)
def session_compatibility(wanted,occupied,margin=10,transitions=()):
    ex=[]; rv=[]
    if not wanted or not isinstance(occupied,list): return result([],['Séances/EDT inconnus : contrôle conservateur des dates'])
    clock=clock_review(wanted+occupied)
    if clock: return result([],[clock])
    for a in wanted:
        for b in occupied:
            if a['date']!=b['date']: continue
            if a['start']<b['end'] and b['start']<a['end']: ex.append('Conflit horaire EDT'); continue
            if a['school_id']==b['school_id']: continue
            frm,to,gap=(b['school_id'],a['school_id'],minutes(a['start'])-minutes(b['end'])) if b['end']<=a['start'] else (a['school_id'],b['school_id'],minutes(b['start'])-minutes(a['end']))
            r=next((r for r in transitions if r.get('from')==frm and r.get('to')==to and r.get('date')==a['date'] and r.get('status')=='ok' and r.get('validated') is True and type(r.get('duration_seconds')) in (int,float) and 0<=r['duration_seconds']<float('inf')),None)
            if not r: rv.append('Transition intersites : trajet réel validé + marge manquants')
            elif r['duration_seconds']+margin*60>gap*60: ex.append('Transition intersites : trajet réel + marge dépasse le créneau')
    return result(ex,rv)

def business_check(n,s,t,b,assignments=(),now=None):
    now=dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    if not b or b['config']['mode']=='historical': return dict(status='eligible',reasons=['Démo simple historique : contrôles administratifs non effectués'],review_flags=[])
    c=b['config']; p=next((p for p in b['profiles'] if p['teacher_id']==t['id']),None); ex=[]; rv=[]
    def stale(v): return not v or timestamp(v)>now or now-timestamp(v)>c['freshness_days']*86400
    if c['state']!='validated' or not c['source_reference'] or not c['validated_on'] or dt.datetime.fromisoformat(c['validated_on']).replace(tzinfo=dt.timezone.utc).timestamp()>now: rv.append('Configuration draft/non validée ou référence/date manquante')
    if not c['academy'] or not c['school_ids']: rv.append('Périmètre configuré inconnu')
    elif s['academy']!=c['academy'] or s['id'] not in c['school_ids']: ex.append('Besoin hors périmètre métier configuré')
    if not n.get('mission_type') or n['mission_type']=='unknown': rv.append('Circuit de mission non renseigné')
    elif n['mission_type'] not in c['mission_modes']: ex.append('Circuit désactivé')
    if not p: return result(ex,rv+['Dossier administratif DEMO inconnu'])
    if stale(p['source_updated_at']): rv.append('Dossier source périmé/inconnu ou daté dans le futur')
    if p['status']=='unknown': rv.append('Statut non renseigné')
    if not p['rad_school_id']: rv.append('RAD non renseigné')
    local=[a for a in assignments if a['teacher_id']==t['id'] and overlap(a,n)]
    if not p['capacity_validated'] or p['capacity_hours'] is None: rv.append('Capacité déclarée non validée')
    elif p['capacity_hours']<n['hours']+sum(a['hours'] for a in local): ex.append('Capacité métier hebdomadaire insuffisante (missions locales incluses)')
    if c['mobility_mode']!='car' or 'car' not in p['mobility_modes']: rv.append('Mobilité voiture non validée : revue manuelle')
    if s['academy']!=t['academy'] and not(p['cross_academy'] and t['cross_academy'] and n.get('allow_cross_academy')): ex.append('Permissions interacadémiques mutuelles manquantes')
    zones={z['id']:z for z in b['zones']}
    def covers(ids): return any(z and (s['id'] in z['school_ids'] or any(s['id'] in zones[a]['school_ids'] for a in z['adjacent_zone_ids'])) for z in (zones.get(i) for i in ids))
    if n.get('mission_type')=='rectoral':
        if p['status']=='RCD': ex.append('Volontaire RCD : circuit rectoral non autorisé')
        if p['status']=='TZR':
            if not p['zone_ids']: rv.append('Zone TZR inconnue')
            elif not covers(p['zone_ids']): (ex if c['out_of_zone']=='exclude' else rv).append('Hors zone TZR et zones limitrophes explicitement autorisées')
        if p['status']=='contractual':
            k=p['contract']
            if not k: rv.append('Contrat inconnu')
            else:
                if not k['validated']: rv.append('Contrat non validé')
                if n['start_date']<k['start_date'] or n['end_date']>k['end_date']: ex.append('Besoin hors dates du contrat')
                if not k['school_ids'] and not k['zone_ids']: rv.append('Périmètre contractuel inconnu')
                elif s['id'] not in k['school_ids'] and not covers(k['zone_ids']): ex.append('Site hors périmètre du contrat')
    if n.get('mission_type')=='RCD':
        if (dt.date.fromisoformat(n['end_date'])-dt.date.fromisoformat(n['start_date'])).days+1>c['rcd_max_days']: rv.append('Seuil RCD indicatif dépassé : requalification proposée, jamais automatique')
        if p['status']!='RCD': ex.append('RCD interne : statut volontaire RCD requis dans ce prototype')
        e=p['rcd_engagement']
        if not e or not e['validated']: rv.append('Engagement/conditions RCD non validés')
        if e:
            if e['school_id']!=s['id']: ex.append('RCD interne : établissement engagement différent')
            if n['start_date']<e['start_date'] or n['end_date']>e['end_date']: ex.append('Hors dates engagement RCD')
            if not n.get('sessions'): rv.append('RCD : séances requises pour contrôler le solde engagement')
            elif e['hours_done']+e['hours_reserved']+local_rcd_hours(assignments,t['id'],e)+session_hours(n['sessions'])>e['hours_limit']: ex.append('Solde engagement RCD insuffisant (prévu distinct du service fait)')
    if p['availability'] and (n['start_date']<p['availability']['start_date'] or n['end_date']>p['availability']['end_date']): ex.append('Indisponibilité manuelle sur la période')
    tt=p['timetable']
    def add(r):
        if r['status']=='excluded': ex.extend(r['reasons'])
        elif r['status']=='review': rv.extend(r['reasons'])
    if tt and tt['known']:
        if stale(tt['source_updated_at']): rv.append('Source EDT périmée/inconnue')
        add(session_compatibility(n.get('sessions'),tt['sessions'],c['travel_margin_minutes']))
    if re.search('guadeloupe|martinique|guyane|réunion|reunion|mayotte|calédonie|caledonie|polynésie|polynesie|wallis|saint.pierre',s['academy'] or '',re.I): rv.append('Territoire hors convention Europe/Paris prise en charge : revue manuelle')
    clock=clock_review(n.get('sessions'))
    if clock: rv.append(clock)
    for a in local: add(session_compatibility(n.get('sessions'),a.get('sessions'),c['travel_margin_minutes']) if tt and tt['known'] else result(['Affectation chevauchante : EDT inconnu'],[]))
    return result(ex,rv)

def effective_teachers(schools,teachers,b):
    if b['config']['mode']!='controlled': return teachers
    sites={s['id']:s for s in schools}; profiles={p['teacher_id']:p for p in b['profiles']}; out=[]
    for t in teachers:
        t=dict(t); p=profiles.get(t['id'])
        if p:
            rad=sites.get(p['rad_school_id'])
            if rad: t.update(lat=rad.get('lat'),lon=rad.get('lon'),base_label=f"RAD fictif déclaré · {rad['name']} · {rad['city']}")
            if p['capacity_hours'] is not None: t['capacity_hours']=p['capacity_hours']
            if p['availability']: t.update(available_from=p['availability']['start_date'],available_until=p['availability']['end_date'])
        out.append(t)
    return out

def context_fingerprint(schools,teachers,assignments,b,now=None):
    now=dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    def stale(v): return not v or timestamp(v)>now or now-timestamp(v)>b['config']['freshness_days']*86400
    freshness=[[p['teacher_id'],stale(p['source_updated_at']),stale(p['timetable']['source_updated_at']) if p['timetable'] and p['timetable']['known'] else None] for p in b['profiles']]
    validated_on=b['config']['validated_on']
    validation_future=bool(validated_on and timestamp(validated_on+'T00:00:00Z')>now)
    data=[b,freshness,validation_future,schools,teachers,[{k:v for k,v in a.items() if k!='route'} for a in assignments]]
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
