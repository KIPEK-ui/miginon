from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from farms.kenya_data import COUNTY_TOWNS
from farms.models import Farm, FarmMembership, FarmRole

from .models import AgriCenter, CropSuitability, DiseaseCatalog, Guide, LearningLesson, LearningPath
from .services import nearest_agri_centers, recommended_crops_for_county

# Nairobi and Eldoret - a known real-world distance (~300km) used to sanity
# check the haversine ranking without hand-computing coordinates.
NAIROBI = (Decimal('-1.28333'), Decimal('36.81667'))
ELDORET = (Decimal('0.51667'), Decimal('35.26667'))
MOMBASA = (Decimal('-4.05000'), Decimal('39.66667'))


class NearestAgriCentersTests(TestCase):
    def setUp(self):
        # advisory.0002_seed_content pre-loads real AgriCenter rows - cleared
        # here so this test's distance/ranking assertions are against a known
        # fixture, not whatever real reference data happens to be seeded.
        AgriCenter.objects.all().delete()
        self.user = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.farm = Farm.objects.create(
            name='Advisory Farm', owner=self.user, latitude=NAIROBI[0], longitude=NAIROBI[1],
        )
        self.eldoret_center = AgriCenter.objects.create(
            name='Eldoret Center', county='Uasin Gishu', latitude=ELDORET[0], longitude=ELDORET[1],
        )
        self.mombasa_center = AgriCenter.objects.create(
            name='Mombasa Center', county='Mombasa', latitude=MOMBASA[0], longitude=MOMBASA[1],
        )

    def test_no_coordinates_returns_empty(self):
        self.farm.latitude = None
        self.farm.longitude = None
        self.farm.save(update_fields=['latitude', 'longitude'])
        self.assertEqual(nearest_agri_centers(self.farm), [])

    def test_ranks_nearer_center_first(self):
        results = nearest_agri_centers(self.farm)
        self.assertEqual(results[0]['center'], self.eldoret_center)
        self.assertEqual(results[1]['center'], self.mombasa_center)

    def test_distance_is_roughly_correct(self):
        # Straight-line (great-circle) distance, not road distance - Nairobi
        # to Eldoret is ~264km as the crow flies, vs. ~312km by road.
        results = nearest_agri_centers(self.farm)
        eldoret_result = next(r for r in results if r['center'] == self.eldoret_center)
        self.assertAlmostEqual(eldoret_result['distance_km'], 264, delta=15)

    def test_limit_is_respected(self):
        for i in range(10):
            AgriCenter.objects.create(
                name=f'Center {i}', county='Nairobi', latitude=NAIROBI[0], longitude=NAIROBI[1],
            )
        results = nearest_agri_centers(self.farm, limit=3)
        self.assertEqual(len(results), 3)


class AdvisoryViewTests(TestCase):
    def setUp(self):
        # Same isolation rationale as NearestAgriCentersTests above - the
        # seed migration's real content would otherwise make exact-count
        # assertions depend on however many reference rows happen to exist.
        DiseaseCatalog.objects.all().delete()
        Guide.objects.all().delete()
        self.user = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.farm = Farm.objects.create(name='Advisory Farm', owner=self.user)
        FarmMembership.objects.create(user=self.user, farm=self.farm, role=FarmRole.FARMER)
        self.client.force_login(self.user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

        self.disease = DiseaseCatalog.objects.create(
            category=DiseaseCatalog.Category.DAIRY, name='Mastitis', affected='Dairy cattle',
            symptoms='Swollen udder', prevention='Clean milking', treatment='Antibiotics',
        )
        self.guide = Guide.objects.create(
            category=Guide.Category.SILAGE, title='Making silage', summary='How to make silage',
            steps='Chop\nPack\nSeal',
        )

    def test_home_counts_are_correct(self):
        response = self.client.get('/advisory/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['dairy_disease_count'], 1)
        self.assertEqual(response.context['crop_disease_count'], 0)
        self.assertEqual(response.context['guide_count'], 1)

    def test_disease_list_filters_by_category(self):
        DiseaseCatalog.objects.create(
            category=DiseaseCatalog.Category.CROP, name='Maize streak virus', affected='Maize',
            symptoms='Streaks', prevention='Resistant seed', treatment='None',
        )
        response = self.client.get('/advisory/diseases/?category=dairy')
        self.assertEqual(len(response.context['diseases']), 1)
        self.assertEqual(response.context['diseases'][0], self.disease)

    def test_disease_detail_renders(self):
        response = self.client.get(f'/advisory/diseases/{self.disease.id}/')
        self.assertEqual(response.status_code, 200)

    def test_guide_detail_renders(self):
        response = self.client.get(f'/advisory/guides/{self.guide.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['guide'].steps_list(), ['Chop', 'Pack', 'Seal'])

    def test_agri_centers_view_renders_with_no_coordinates(self):
        response = self.client.get('/advisory/agri-centers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['results'], [])


class LearningPathViewTests(TestCase):
    def setUp(self):
        # Isolated from the seed migration's real "getting-started" path for
        # the same reason as AdvisoryViewTests above.
        LearningPath.objects.all().delete()
        self.user = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.farm = Farm.objects.create(name='Advisory Farm', owner=self.user)
        FarmMembership.objects.create(user=self.user, farm=self.farm, role=FarmRole.FARMER)
        self.client.force_login(self.user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

        self.path = LearningPath.objects.create(
            slug='test-path', title='Test path', description='A test learning path.',
        )
        self.lesson = LearningLesson.objects.create(
            path=self.path, order=1, title='First lesson', summary='Intro',
            content='Intro paragraph.\n## A heading\nA bullet point.',
            key_terms='DIM: Days in milk.',
        )

    def test_learning_path_list_renders(self):
        response = self.client.get('/advisory/learning/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.path, response.context['paths'])

    def test_learning_path_detail_lists_lessons(self):
        response = self.client.get(f'/advisory/learning/{self.path.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.lesson, response.context['lessons'])

    def test_lesson_detail_parses_content_and_key_terms(self):
        response = self.client.get(f'/advisory/learning/{self.path.slug}/{self.lesson.order}/')
        self.assertEqual(response.status_code, 200)
        blocks = response.context['lesson'].content_blocks()
        self.assertEqual(blocks[0], {'heading': False, 'text': 'Intro paragraph.'})
        self.assertEqual(blocks[1], {'heading': True, 'text': 'A heading'})
        self.assertEqual(
            response.context['lesson'].key_terms_list(), [{'term': 'DIM', 'definition': 'Days in milk.'}]
        )


class CropSuitabilitySeedDataTests(TestCase):
    """Runs against the real seeded data (advisory/migrations/
    0004_seed_crop_suitability.py applies like any other migration when the
    test DB is built) - a data-integrity check on the seed content itself,
    not just the service function's plumbing."""

    def test_every_county_has_at_least_one_recommendation(self):
        missing = [county for county in COUNTY_TOWNS if not CropSuitability.objects.filter(county=county).exists()]
        self.assertEqual(missing, [], f'Counties with no seeded crop suitability rows: {missing}')

    def test_known_highland_county_recommends_tea(self):
        crops = [c.crop_name for c in recommended_crops_for_county('Kiambu')]
        self.assertIn('Tea', crops)

    def test_known_asal_county_recommends_sorghum(self):
        crops = [c.crop_name for c in recommended_crops_for_county('Turkana')]
        self.assertIn('Sorghum', crops)


class RecommendedCropsForCountyTests(TestCase):
    def test_blank_county_returns_empty(self):
        self.assertEqual(recommended_crops_for_county(''), [])

    def test_unknown_county_returns_empty(self):
        self.assertEqual(recommended_crops_for_county('Not A Real County'), [])
