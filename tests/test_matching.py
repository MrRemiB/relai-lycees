import unittest
from matching import match_candidates, validate_need

SCHOOL = dict(id='S1', name='Lycée test', city='Dijon', academy='Dijon', sector='Public', lat=47.32, lon=5.04, pathways=['Générale'])
NEED = dict(school_id='S1', subject='Mathématiques', pathway='Générale', start_date='2026-10-10', end_date='2026-10-20', hours=12, allow_cross_academy=False)
TEACHER = dict(id='DEMO-0001', name='Profil démo 0001', subjects=['Mathématiques'], academy='Dijon', sector='Public', lat=47.32, lon=5.04, base_label='Ancrage administratif démo', capacity_hours=18, max_distance_km=100, available_from='2026-01-01', available_until='2028-12-31', pathways=['Générale'], cross_academy=False)

class MatchingTests(unittest.TestCase):
    def match(self, teachers=None, school=None, assignments=None, **updates):
        return match_candidates(dict(NEED, **updates), school or SCHOOL, teachers or [TEACHER], assignments or [], 150)

    def test_eligible_and_stable_ranking(self):
        result = self.match([dict(TEACHER, id='B', capacity_hours=20), dict(TEACHER, id='A', capacity_hours=20), TEACHER])
        self.assertEqual([c['teacher']['id'] for c in result['candidates']], ['A','B','DEMO-0001'])
        self.assertEqual(result['summary']['eligible'], 3)

    def test_every_hard_constraint_excludes(self):
        for changes in [dict(subjects=['Anglais']), dict(pathways=['Professionnelle']), dict(sector='Privé'), dict(academy='Paris'), dict(available_from='2026-10-11'), dict(available_until='2026-10-19'), dict(capacity_hours=10), dict(lat=48.5, max_distance_km=1)]:
            with self.subTest(changes=changes):
                r=self.match([dict(TEACHER, **changes)])
                self.assertFalse(r['candidates'])
                self.assertTrue(r['excluded'][0]['reasons'])

    def test_cross_academy_requires_both_optins(self):
        t=dict(TEACHER, academy='Paris', cross_academy=True)
        self.assertFalse(self.match([t])['candidates'])
        self.assertTrue(self.match([t], allow_cross_academy=True)['candidates'])

    def test_inclusive_overlap_blocks_even_spare_capacity(self):
        a=dict(teacher_id=TEACHER['id'], start_date='2026-10-20', end_date='2026-10-25', hours=1)
        self.assertFalse(self.match(assignments=[a])['candidates'])
        a['start_date']='2026-10-21'
        self.assertTrue(self.match(assignments=[a])['candidates'])

    def test_missing_school_coordinates_never_fabricates_distance(self):
        r=self.match(school=dict(SCHOOL,lat=None,lon=None))
        self.assertFalse(r['candidates'])
        self.assertIsNone(r['excluded'][0]['distance_km'])

    def test_unknown_sector_is_hard_ineligible(self):
        r=self.match(school=dict(SCHOOL,sector=None),teachers=[dict(TEACHER,sector=None)])
        self.assertFalse(r['candidates'])

    def test_validation_rejects_malformed_inputs(self):
        for changes in [dict(subject='Unknown'),dict(pathway='Unknown'),dict(hours=10**1000),dict(hours=True),dict(hours=float('nan')),dict(hours=0),dict(hours=61),dict(start_date='2026-02-30'),dict(start_date='2026-10-21'),dict(allow_cross_academy='false'),dict(max_distance_km=False),dict(max_distance_km=float('inf'))]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_need(dict(NEED,**changes),{'S1':SCHOOL})

if __name__ == '__main__': unittest.main()
