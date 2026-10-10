"""Conservative, explainable demo matching; never reconstruct a timetable."""
import math
import datetime as dt

SUBJECTS = ['Mathématiques','Lettres modernes','Anglais','Histoire-géographie','Physique-chimie','SVT','SES','Philosophie','Économie-gestion','EPS','Sciences industrielles']
PATHWAYS = ['Générale','Technologique','Professionnelle']
METHOD = 'Distance à vol d’oiseau (haversine), puis capacité décroissante, puis identifiant. Toute affectation dont les dates se chevauchent est bloquée, même avec des heures restantes : aucun emploi du temps réel disponible. Validation humaine simulée uniquement.'


def number(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f'{label} doit être un nombre fini entre {low} et {high}.')
    return value


def date(value):
    if not isinstance(value, str):
        raise ValueError('Date ISO YYYY-MM-DD requise.')
    try:
        result = dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError('Date ISO YYYY-MM-DD valide requise.') from None
    if result.isoformat() != value:
        raise ValueError('Date ISO YYYY-MM-DD requise.')
    return value


def boolean(value, label):
    if type(value) is not bool:
        raise ValueError(f'{label} doit être un booléen JSON.')
    return value


def coordinates(lat, lon):
    if lat is None or lon is None:
        return False
    number(lat, 'Latitude', -90, 90)
    number(lon, 'Longitude', -180, 180)
    return True


def need_identifier(value):
    # SQLite INTEGER is signed 64-bit; Python JSON integers are unbounded.
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        raise ValueError('Identifiant de besoin hors plage SQLite.')
    return value


def validate_need(payload, schools, creation=False):
    if not isinstance(payload, dict):
        raise ValueError('Objet JSON requis.')
    allowed = {'school_id','subject','pathway','start_date','end_date','hours','allow_cross_academy','urgency'} if creation else {'school_id','subject','pathway','start_date','end_date','hours','allow_cross_academy','max_distance_km','need_id'}
    allowed.update({'max_travel_minutes','mission_type','sessions'})
    if 'mission_type' in payload and payload['mission_type'] not in ('RCD','rectoral','unknown'): raise ValueError('Circuit inconnu.')
    if 'sessions' in payload:
        from business import validate_sessions
        validate_sessions(payload['sessions'],list(schools.values()),payload)
        if any(s['school_id']!=payload.get('school_id') for s in payload['sessions']): raise ValueError('Site de séance différent du besoin.')
    number(payload.get('max_travel_minutes',90),'Trajet maximum (minutes)',0,480)
    if set(payload) - allowed:
        raise ValueError('Champs inconnus.')
    school = schools.get(payload.get('school_id')) if isinstance(payload.get('school_id'), str) else None
    if not school:
        raise ValueError('Établissement inconnu.')
    if payload.get('subject') not in SUBJECTS or payload.get('pathway') not in PATHWAYS:
        raise ValueError('Discipline ou voie inconnue.')
    if payload['pathway'] not in school.get('pathways', []):
        raise ValueError('Voie non proposée par cet établissement.')
    start, end = date(payload.get('start_date')), date(payload.get('end_date'))
    if start > end:
        raise ValueError('La fin doit suivre le début.')
    number(payload.get('hours'), 'Heures hebdomadaires', 0.1, 60)
    boolean(payload.get('allow_cross_academy', False), 'allow_cross_academy')
    if creation and payload.get('urgency', 'Normale') not in ['Normale','Urgente']:
        raise ValueError('Urgence inconnue.')
    if not creation:
        number(payload.get('max_distance_km', 150), 'Rayon', 0, 2000)
        if 'need_id' in payload:
            need_identifier(payload['need_id'])
    coordinates(school.get('lat'), school.get('lon'))
    result = dict(payload)
    result['max_travel_minutes'] = payload.get('max_travel_minutes',90)
    result['allow_cross_academy'] = payload.get('allow_cross_academy', False)
    if creation:
        result['urgency'] = payload.get('urgency', 'Normale')
    return result


def distance_km(lat1, lon1, lat2, lon2):
    a,b,c,d = map(math.radians, (lat1,lon1,lat2,lon2))
    h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371.0088*2*math.asin(math.sqrt(min(1,max(0,h))))


def match_candidates(need, school, teachers, assignments, max_distance_km=150, business=None, now=None):
    from business import business_check
    candidates, excluded, counts, review = [], [], {}, []
    number(max_distance_km, 'Rayon', 0, 2000)
    for teacher in teachers:
        reasons=[]
        dist=None
        if coordinates(school.get('lat'),school.get('lon')) and coordinates(teacher.get('lat'),teacher.get('lon')):
            dist=distance_km(school['lat'],school['lon'],teacher['lat'],teacher['lon'])
        else:
            reasons.append('Coordonnées indisponibles')
        if need['subject'] not in teacher['subjects']: reasons.append('Discipline incompatible')
        if need['pathway'] not in teacher['pathways']: reasons.append('Voie incompatible')
        if school['sector'] not in ['Public','Privé'] or teacher['sector'] not in ['Public','Privé']: reasons.append('Secteur inconnu : compatibilité non vérifiable')
        elif school['sector'] != teacher['sector']: reasons.append('Secteur incompatible')
        if school['academy'] != teacher['academy'] and not (teacher['cross_academy'] and need.get('allow_cross_academy', False)): reasons.append('Académie incompatible')
        if teacher['available_from'] > need['start_date'] or teacher['available_until'] < need['end_date']: reasons.append('Disponibilité insuffisante')
        if teacher['capacity_hours'] < need['hours']: reasons.append('Capacité hebdomadaire insuffisante')
        if dist is not None and dist > teacher['max_distance_km']: reasons.append('Hors mobilité du profil')
        if dist is not None and dist > max_distance_km: reasons.append('Hors rayon du besoin')
        if (not business or business['config']['mode']=='historical') and any(a['teacher_id']==teacher['id'] and a['start_date'] <= need['end_date'] and a['end_date'] >= need['start_date'] for a in assignments): reasons.append('Affectation sur une période chevauchante')
        controlled=business_check(need,school,teacher,business,assignments,now)
        if controlled['status']=='excluded': reasons.extend(controlled['reasons'])
        if reasons:
            for reason in reasons: counts[reason]=counts.get(reason,0)+1
            excluded.append(dict(teacher_id=teacher['id'],name=teacher['name'],distance_km=round(dist,2) if dist is not None else None,reasons=reasons))
        elif controlled['status']=='review':
            review.append(dict(teacher_id=teacher['id'],name=teacher['name'],distance_km=round(dist,2),**controlled))
        else:
            candidates.append(dict(teacher=teacher,distance_km=round(dist,2),reasons=['Discipline, voie, secteur et académie compatibles','Disponible sur toute la période','Capacité déclarée et conflits EDT/dates vérifiés (simulation)' if business and business['config']['mode']=='controlled' else 'Capacité suffisante et aucune affectation chevauchante','Distance dans les deux rayons de mobilité'],_distance=dist))
            if business is not None: candidates[-1].update(business_status='eligible',review_flags=[],business_reasons=controlled['reasons'])
    candidates.sort(key=lambda c:(c['_distance'],-c['teacher']['capacity_hours'],c['teacher']['id']))
    for c in candidates: del c['_distance']
    output=dict(candidates=candidates,excluded=excluded,summary=dict(eligible=len(candidates),total=len(teachers),exclusions=counts),method=METHOD)
    if business is not None: output['review']=review; output['summary']['review']=len(review)
    return output


def match_routed_candidates(need, school, teachers, assignments, router, max_distance_km=150, business=None):
    result=match_candidates(need,school,teachers,assignments,max_distance_km,business)
    base=result['candidates']; offered=[]; calculated=unavailable=deferred=0
    maximum=number(need.get('max_travel_minutes',90),'Trajet maximum',0,480)*60
    pairs=[((c['teacher']['lon'],c['teacher']['lat']),(school['lon'],school['lat'])) for c in base]
    try:
        routes=router.route_many(pairs)
        if len(routes)!=len(base): raise ValueError('Incomplete router response')
    except Exception:
        routes=[dict(status='unavailable',duration_seconds=None) for _ in base]
    for candidate,route in zip(base,routes):
        status=route.get('status'); reason=None
        if status=='ok':
            calculated+=1
            if route['duration_seconds']>maximum: reason='Temps de trajet supérieur au maximum'
            else:
                candidate.update(straight_line_km=candidate['distance_km'],duration_seconds=route['duration_seconds'],duration_minutes=route['duration_seconds']/60,road_distance_km=route['road_distance_km'],route={k:v for k,v in route.items() if k not in ('duration_seconds','road_distance_km')})
                candidate['reasons'].append('Temps de trajet estimé dans le maximum demandé')
                offered.append(candidate)
        elif status=='deferred':
            deferred+=1; reason='Calcul différé : budget ou délai de calcul atteint, réessayez'
        else:
            unavailable+=1; reason='Itinéraire indisponible'
        if reason:
            result['excluded'].append(dict(teacher_id=candidate['teacher']['id'],name=candidate['teacher']['name'],distance_km=candidate['distance_km'],straight_line_km=candidate['distance_km'],duration_seconds=None,route_status=status,reasons=[reason]))
            counts=result['summary']['exclusions']; counts[reason]=counts.get(reason,0)+1
    offered.sort(key=lambda c:(c['duration_seconds'],c['road_distance_km'],-c['teacher']['capacity_hours'],c['teacher']['id']))
    partial=bool(deferred or any(r.get('status') not in ('ok','no_route') for r in routes))
    result['candidates']=offered
    result['summary'].update(eligible=len(offered),compatible_before_routing=len(base),routes_calculated=calculated,routes_unavailable=unavailable,routes_deferred=deferred)
    result['routing']=dict(provider='IGN Géoplateforme',profile='car',traffic=False,partial=partial,warning='Comparaison partielle : le classement porte uniquement sur les trajets calculés. Réessayez pour compléter les calculs.' if partial else None,requested=len(base),calculated=calculated,unavailable=unavailable,deferred=deferred)
    result['method']='Temps de trajet estimé en voiture, sans trafic en temps réel ; secondes exactes, puis distance routière, capacité décroissante et identifiant. Toute affectation dont les dates se chevauchent est bloquée : aucun emploi du temps réel disponible. Validation humaine simulée uniquement.'
    if business and business['config']['mode']=='controlled': result['method']='Temps routier réel IGN puis capacité/identifiant. Règles locales fictives : circuit, RAD, zones, contrat, engagement, fraîcheur, capacité cumulée et EDT. Transitions intersites sans preuve dédiée et fuseaux/DST non pris en charge : revue. Aucune conformité réglementaire, affectation officielle ou paie.'
    return result
