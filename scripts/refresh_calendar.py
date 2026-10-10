#!/usr/bin/env python3
"""Refresh the official school calendar (advisory only, no staffing exclusion)."""
import datetime as dt
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-calendrier-scolaire'

def main():
    with urlopen(BASE + '/exports/json', timeout=90) as response:
        payload = response.read()
        if payload[:2] == b'\x1f\x8b':
            import gzip
            payload = gzip.decompress(payload)
        rows = json.loads(payload)
    with urlopen(BASE + '/records?limit=1', timeout=40) as response:
        payload = response.read()
        if payload[:2] == b'\x1f\x8b':
            import gzip
            payload = gzip.decompress(payload)
        expected = json.loads(payload)['total_count']
    assert len(rows) == expected, (len(rows), expected)
    with urlopen(BASE, timeout=40) as response:
        payload = response.read()
        if payload[:2] == b'\x1f\x8b':
            import gzip
            payload = gzip.decompress(payload)
        official_meta = json.loads(payload)['metas']['default']
    metadata = {'dataset_url': 'https://data.education.gouv.fr/explore/dataset/fr-en-calendrier-scolaire/',
                'license': official_meta.get('license'),
                'license_url': official_meta.get('license_url'),
                'source_timezone': official_meta.get('timezone'),
                'source_modified_at': official_meta.get('modified'),
                'source_url': BASE + '/exports/json',
                'retrieved_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'count':len(rows), 'school_years':sorted(set(r['annee_scolaire'] for r in rows)),
                'advisory_only':True,
                'date_note':'Official timestamps preserved. School calendars vary by academy; consult official dates. No automatic exclusion.'}
    (ROOT/'data').mkdir(exist_ok=True)
    out = ROOT/'data/calendar.json'
    out.write_text(json.dumps({'metadata':metadata,'holidays':rows}, ensure_ascii=False),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
