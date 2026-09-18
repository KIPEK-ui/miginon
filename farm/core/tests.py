from django.core.management import call_command
from django.test import TestCase

from cows.models import Cow
from creditscore.models import CreditScoreSnapshot
from farms.models import Farm

from .demo import DEMO_USER_EMAIL, get_or_create_demo_farm, is_demo_user


class DemoFarmSeedTests(TestCase):
    """core.demo.get_or_create_demo_farm backs both /demo/ (lazy, first
    visit) and the optional seed_demo_farm command - both paths have to be
    idempotent, since a management command run ahead of time and the first
    real visitor could otherwise race to create two demo farms."""

    def test_creates_a_populated_farm_exactly_once(self):
        farm_1, user_1 = get_or_create_demo_farm()
        farm_2, user_2 = get_or_create_demo_farm()

        self.assertEqual(farm_1.id, farm_2.id)
        self.assertEqual(user_1.id, user_2.id)
        self.assertEqual(Farm.objects.filter(owner__email=DEMO_USER_EMAIL).count(), 1)
        self.assertTrue(Cow.objects.filter(farm=farm_1).exists())
        self.assertTrue(CreditScoreSnapshot.objects.filter(farm=farm_1).exists())

    def test_seed_demo_farm_command_is_idempotent(self):
        call_command('seed_demo_farm')
        call_command('seed_demo_farm')
        self.assertEqual(Farm.objects.filter(owner__email=DEMO_USER_EMAIL).count(), 1)


class DemoLoginViewTests(TestCase):
    def test_visiting_demo_logs_in_as_the_demo_user_and_redirects_to_dashboard(self):
        response = self.client.get('/demo/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(is_demo_user(response.wsgi_request.user))
        self.assertRedirects(response, '/farm/')


class DemoModeMiddlewareTests(TestCase):
    """The whole safety story for leaving /demo/ open to the public: the
    demo account can navigate anywhere (GET) but can't mutate farm data
    (POST), while still being able to log itself out or a real visitor
    log in as themselves from the same browser."""

    def setUp(self):
        self.client.get('/demo/')  # logs the test client in as the demo account

    def test_demo_account_cannot_create_a_cow(self):
        farm, _user = get_or_create_demo_farm()
        before = Cow.objects.filter(farm=farm).count()
        self.client.post('/cows/add/', {'tag_id': 'HACKED-1', 'breed': 'Friesian', 'block': ''})
        self.assertEqual(Cow.objects.filter(farm=farm).count(), before)

    def test_demo_account_can_still_view_pages(self):
        response = self.client.get('/farm/')
        self.assertEqual(response.status_code, 200)

    def test_demo_account_can_toggle_theme(self):
        response = self.client.post('/theme/', follow=True)
        self.assertEqual(response.status_code, 200)

    def test_demo_account_can_log_out(self):
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logging_out_of_the_demo_lets_a_real_login_proceed_normally(self):
        # login/signup views redirect ANY already-authenticated user
        # (accounts.views._already_authenticated_redirect) regardless of
        # demo status, so the allowlist for them only matters once the
        # demo account has actually logged out - confirm that handoff
        # isn't left in some broken state by the middleware.
        self.client.post('/accounts/logout/')
        response = self.client.post('/accounts/login/', {'code': 'NOPE0000'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Double-check the code')


class LandingPageTests(TestCase):
    def test_landing_page_renders_with_demo_and_partner_links(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/demo/')
        self.assertContains(response, '/credit-score/partners/apply/')
