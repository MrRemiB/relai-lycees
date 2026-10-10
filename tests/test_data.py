"""Offline contracts for shipped genuine education snapshots."""
import datetime as dt
import json
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class OfficialDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.school_data = json.loads((ROOT/'data/schools.json').read_text(encoding='utf-8'))
        cls.calendar = json.loads((ROOT/'data/calendar.json').read_text(encoding='utf-8'))

    def test_all_school_ids_preserved_and_unique(self):
        rows = self.school_data['schools']
        self.assertEqual(len(rows), self.school_data['metadata']['count'])
        self.assertEqual(len(rows), len({r['id'] for r in rows}))
        self.assertTrue(all(re.fullmatch(r'\d{7}[A-Z]', r['id']) for r in rows))
        self.assertGreaterEqual(self.school_data['metadata']['total_source'],len(rows))

    def test_coordinates_and_missing_school_count(self):
        rows=self.school_data['schools']
        mapped=0
        for row in rows:
            lat,lon=row['lat'],row['lon']
            self.assertEqual(lat is None,lon is None)
            if lat is not None:
                self.assertTrue(math.isfinite(lat) and -90 <= lat <= 90)
                self.assertTrue(math.isfinite(lon) and -180 <= lon <= 180)
                mapped+=1
        self.assertEqual(mapped,self.school_data['metadata']['coordinate_count'])
        self.assertEqual(len(rows)-mapped,self.school_data['metadata']['missing_coordinates'])

    def test_no_inferred_sector_or_pathway(self):
        for row in self.school_data['schools']:
            self.assertIn(row['sector'],('Public','Privé',None))
            self.assertLessEqual(set(row['pathways']),{'Générale','Technologique','Professionnelle'})
        self.assertTrue(any(r['sector'] is None for r in self.school_data['schools']))

    def test_offshore_rows_not_lost_to_mainland_box(self):
        academies={row['academy'] for row in self.school_data['schools']}
        self.assertIn('La Réunion',academies)
        self.assertIn('Guadeloupe',academies)
        self.assertTrue(any(r['lat'] is not None and r['lat'] < 0 for r in self.school_data['schools']))

    def test_calendar_complete_valid_intervals_and_real_license(self):
        holidays=self.calendar['holidays']
        self.assertEqual(len(holidays),self.calendar['metadata']['count'])
        self.assertEqual(self.calendar['metadata']['license'],'Licence Ouverte v2.0 (Etalab)')
        self.assertEqual(self.calendar['metadata']['source_timezone'],'Europe/Paris')
        for row in holidays:
            # Source includes single-date milestones (e.g. Début des Vacances).
            self.assertLessEqual(dt.datetime.fromisoformat(row['start_date']),dt.datetime.fromisoformat(row['end_date']))
            self.assertTrue(row['location'])
        self.assertIn('2026-2027',self.calendar['metadata']['school_years'])

    def test_paris_calendar_timestamp_is_not_raw_utc_date(self):
        from zoneinfo import ZoneInfo
        example=next(r for r in self.calendar['holidays'] if r['location']=='Dijon' and r['annee_scolaire']=='2026-2027' and 'Toussaint' in r['description'])
        local=dt.datetime.fromisoformat(example['start_date']).astimezone(ZoneInfo('Europe/Paris')).date()
        self.assertNotEqual(local.isoformat(),example['start_date'][:10])

if __name__=='__main__':
    unittest.main()
