"""Deterministic anonymous administrative school-anchor profiles, not people."""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matching import SUBJECTS, PATHWAYS, coordinates


def generate_teachers(schools, count=1600, today=None):
    today=today or dt.date.today()
    anchors=sorted([s for s in schools if s.get('sector') in ['Public','Privé'] and coordinates(s.get('lat'),s.get('lon'))],key=lambda s:(s['academy'],s['id']))
    if not anchors:
        raise ValueError('Aucun établissement géolocalisé : génération impossible.')
    groups={}
    for s in anchors: groups.setdefault(s['academy'],[]).append(s)
    academies=sorted(groups)
    result=[]
    for i in range(count):
        academy=academies[i%len(academies)]
        cycle=i//len(academies)
        sectors=sorted({s['sector'] for s in groups[academy]})
        sector=sectors[cycle%len(sectors)]
        sector_cycle=cycle//len(sectors)
        sector_anchors=[s for s in groups[academy] if s['sector']==sector]
        school=sector_anchors[(sector_cycle*17)%len(sector_anchors)]
        # Each academy/known sector receives every discipline; no sector inference.
        subject=SUBJECTS[sector_cycle%len(SUBJECTS)]
        result.append(dict(id=f'DEMO-{i+1:04d}',name=f'Profil démo {i+1:04d}',subjects=[subject],academy=academy,sector=school['sector'],lat=school['lat'],lon=school['lon'],base_label=f"Ancrage administratif fictif · {school['name']} · {school['city']}",capacity_hours=[12,18,24][cycle%3],max_distance_km=[80,150,250][cycle%3],available_from=(today-dt.timedelta(days=365)).isoformat(),available_until=(today+dt.timedelta(days=730)).isoformat(),pathways=list(PATHWAYS),cross_academy=cycle%5==0))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schools',type=Path,default=Path(__file__).resolve().parents[1]/'data/schools.json')
    parser.add_argument('--count',type=int,default=1600)
    args=parser.parse_args()
    if not 1000 <= args.count <= 2000: parser.error('count doit être entre 1000 et 2000')
    print(json.dumps({'demo':True,'teachers':generate_teachers(json.loads(args.schools.read_text())['schools'],args.count)},ensure_ascii=False,allow_nan=False))
