#!/usr/bin/env python3
"""Refresh official open lycées; network access uses Python stdlib urllib only."""
import gzip
import json
import math
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = 'https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education'
DATASET_URL = 'https://data.education.gouv.fr/explore/dataset/fr-en-annuaire-education/'
FILTER = "type_etablissement = 'Lycée' AND etat = 'OUVERT'"
QUERY = 'where=' + quote(FILTER, safe='')
SOURCE_URL = API + '/exports/json?' + QUERY
PATHWAYS = [('voie_generale', 'Générale'), ('voie_technologique', 'Technologique'), ('voie_professionnelle', 'Professionnelle')]


def fetch(url):
    for attempt in range(4):
        try:
            request = Request(url, headers={'Accept': 'application/json', 'Accept-Encoding': 'identity', 'User-Agent': 'Relai-Lycees/1.0 (official-data-refresh)'})
            with urlopen(request, timeout=180) as response:
                body = response.read()
                if body[:2] == b'\x1f\x8b':
                    body = gzip.decompress(body)
                return json.loads(body)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if attempt == 3:
                raise
            print(f'Retrying {url}: {exc}', flush=True)
            time.sleep(2 ** attempt)


def coordinates(record):
    position = record.get('position') or {}
    lat = record.get('latitude')
    lon = record.get('longitude')
    if lat is None:
        lat = position.get('lat')
    if lon is None:
        lon = position.get('lon')
    try:
        lat, lon = float(lat), float(lon)
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (TypeError, ValueError):
        pass
    return None, None


def normalize(record):
    uai = record.get('identifiant_de_l_etablissement')
    if not isinstance(uai, str) or not re.fullmatch(r'[0-9]{7}[A-Z]', uai):
        raise ValueError(f'Missing or malformed source UAI: {uai!r}')
    sector = record.get('statut_public_prive')
    # Preserve missing sector rather than invent Public/Privé or drop rows.
    if sector not in ('Public', 'Privé', None):
        raise ValueError(f'Unexpected sector for {uai}: {sector!r}')
    if record.get('type_etablissement') != 'Lycée' or record.get('etat') != 'OUVERT':
        raise ValueError(f'Unfiltered source record: {uai}')
    lat, lon = coordinates(record)
    return {
        'id': uai,
        'name': record.get('nom_etablissement'),
        'city': record.get('nom_commune'),
        'postcode': record.get('code_postal'),
        'address': ', '.join(str(record[key]).strip() for key in ('adresse_1', 'adresse_2', 'adresse_3') if record.get(key)),
        'department': record.get('libelle_departement'),
        'academy': record.get('libelle_academie'),
        'region': record.get('libelle_region'),
        'sector': sector,
        'lat': lat,
        'lon': lon,
        'pathways': [label for key, label in PATHWAYS if str(record.get(key)) == '1'],
        'updated_at': record.get('date_maj_ligne'),
    }


def refresh():
    first_total = fetch(API + '/records?' + QUERY + '&limit=1')['total_count']
    official = {}
    metadata_error = None
    try:
        official = fetch(API).get('metas', {})
    except Exception as exc:
        metadata_error = str(exc)
    defaults = official.get('default', {})
    license_name = defaults.get('license') or 'unknown'
    records = fetch(SOURCE_URL)
    if not isinstance(records, list):
        raise ValueError('Export was not a JSON array')
    last_total = fetch(API + '/records?' + QUERY + '&limit=1')['total_count']
    if len(records) != first_total or first_total != last_total:
        raise ValueError(f'Source changed or incomplete export: before={first_total}, exported={len(records)}, after={last_total}; rerun')

    # Multi-site UAI rows become one school. Prefer latest dated row, then
    # coordinates, then deterministic JSON order; union known pathways.
    grouped = {}
    for record in records:
        school = normalize(record)
        grouped.setdefault(school['id'], []).append(school)
    schools = []
    for uai, rows in sorted(grouped.items()):
        chosen = max(rows, key=lambda s: (s['updated_at'] or '', s['lat'] is not None, json.dumps(s, sort_keys=True, ensure_ascii=False)))
        chosen['pathways'] = [label for _, label in PATHWAYS if any(label in s['pathways'] for s in rows)]
        # Do not lose coordinates when the latest source row is ungeocoded.
        if chosen['lat'] is None:
            located = [s for s in rows if s['lat'] is not None]
            if located:
                other = max(located, key=lambda s: (s['updated_at'] or '', json.dumps(s, sort_keys=True, ensure_ascii=False)))
                for key in ('lat', 'lon', 'address', 'city', 'postcode', 'department', 'academy', 'region'):
                    chosen[key] = other[key]
        schools.append(chosen)
    coordinate_count = sum(s['lat'] is not None and s['lon'] is not None for s in schools)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    envelope = {'metadata': {
        'source_url': SOURCE_URL,
        'dataset_url': DATASET_URL,
        'retrieved_at': retrieved_at,
        'total_source': first_total,
        'count': len(schools),
        'coordinate_count': coordinate_count,
        'missing_coordinates': len(schools) - coordinate_count,
        'license': license_name,
        'filters': FILTER,
    }, 'schools': schools}
    assert len({s['id'] for s in schools}) == len(schools)
    assert sum(len(rows) for rows in grouped.values()) == first_total
    assert coordinate_count + envelope['metadata']['missing_coordinates'] == len(schools)
    duplicates = first_total - len(schools)
    departments = sorted({s['department'] for s in schools if s['department']})
    sources = f'''# Official lycée data

- Publisher: {defaults.get('publisher') or 'unknown'}.
- Dataset: [Annuaire de l’éducation]({DATASET_URL}); source systems: ONISEP and RAMSESE, as stated in official metadata.
- Metadata API: {API}
- Filtered JSON export: {SOURCE_URL}
- Exact filter: `{FILTER}`. No sector, academy, region, department or coordinate filter.
- License: **{license_name}**.
- Official license URL: {defaults.get('license_url') or 'unknown'}.
- Metadata lookup status: {metadata_error or 'successful'}.

## Freshness and completeness

- Retrieval (UTC): {retrieved_at}
- Official dataset modified timestamp: {defaults.get('modified') or 'unknown'}.
- Official stated update frequency: {official.get('dcat', {}).get('accrualperiodicity') or 'unknown'}.
- Verified API `total_count` before and after export: **{first_total}**.
- Downloaded source rows: **{len(records)}**; unique UAI schools: **{len(schools)}**; duplicate UAI rows consolidated: **{duplicates}**.
- Schools with valid WGS84 coordinate pairs: **{coordinate_count}**; missing or invalid coordinate pairs retained: **{len(schools) - coordinate_count}**.
- `updated_at` preserves each chosen row’s `date_maj_ligne`; retrieval time is not a school update date.
- Refresh: `python3 scripts/refresh_schools.py` from the project directory. Uses Python standard library only, urllib for HTTP, retries and gzip handling. A count mismatch aborts before replacing data.

## Normalization and geographic limits

- All official `Lycée` records marked `OUVERT`, both Public and Privé, are included. No bounding box: metropolitan France and overseas records are retained, including territories outside the European map viewport.
- This is the official directory’s coverage, not an independent census. Other source types (e.g. EREA, CFA or colleges) and closed/not-yet-open establishments are outside the exact filter, even if they offer lycée-level instruction. No exhaustive coverage of every overseas territory is implied where the official source has no records.
- Department, academy and region use official text labels; postcode remains a string. UAI is validated and preserved exactly, never synthesized.
- Sector is Public or Privé when declared. **{sum(s['sector'] is None for s in schools)} records have a null official sector**, retained as `sector: null` rather than guessed or excluded. This is an explicit exception to the desired two-value sector schema. Missing-sector UAI: {', '.join(s['id'] for s in schools if s['sector'] is None) or 'none'}.
- Addresses join nonempty `adresse_1`, `adresse_2`, `adresse_3`. Coordinates use official WGS84 latitude/longitude (falling back to `position`), not projected origin coordinates; no external geocoding or guessed positions. Coordinates can have approximate address or commune-level precision and are not guaranteed building locations.
- One record per UAI. Duplicate rows prefer most recent `date_maj_ligne`, then available coordinates, then deterministic lexical JSON order. Known pathway flags are unioned. If needed, use a geocoded duplicate’s coordinates and matching geographic/address fields. This represents one site, not every campus of a multi-site establishment.
- Pathways are included only for official `voie_* = 1`: Générale, Technologique, Professionnelle. An empty list means none affirmed in the source, not independently confirmed absence. Missing textual source facts remain null.
- No teacher, staff, replacement availability or allocation data is present in this official school dataset. Any demo teacher data must be clearly labeled synthetic.

### Department labels present in this snapshot

{', '.join(departments)}
'''
    data_dir = ROOT / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / 'schools.json').write_text(json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (data_dir / 'SOURCES.md').write_text(sources, encoding='utf-8')
    saved = json.loads((data_dir / 'schools.json').read_text(encoding='utf-8'))
    assert saved == envelope
    print(json.dumps(saved['metadata'], ensure_ascii=False, indent=2))
    print(f'Verified {len(schools)} unique schools; {duplicates} duplicate rows consolidated.')


if __name__ == '__main__':
    refresh()
