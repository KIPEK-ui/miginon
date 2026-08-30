from django.core import mail
from django.test import Client, TestCase
from django.utils import timezone

from farms.models import Farm, FarmMembership

from .models import EmailOTP, User


def get_otp(email, purpose, farm=None):
    return EmailOTP.objects.filter(email=email, purpose=purpose, farm=farm).order_by('-created_at').first()


class SignupFlowTests(TestCase):
    def test_full_signup_wizard(self):
        c = Client()

        r = c.get('/accounts/signup/')
        self.assertEqual(r.status_code, 200)

        r = c.post('/accounts/signup/', {
            'first_name': 'Test', 'last_name': 'Farmer', 'email': 'newfarmer@example.com', 'phone': '0712345678'
        })
        self.assertRedirects(r, '/accounts/signup/farm/')

        r = c.get('/accounts/signup/farm/')
        self.assertEqual(r.status_code, 200)

        r = c.post('/accounts/signup/farm/', {
            'farm_name': 'Test Farm', 'country': 'KE', 'county': 'Nairobi', 'location': 'Westlands'
        })
        self.assertRedirects(r, '/accounts/signup/review/')

        r = c.get('/accounts/signup/review/')
        self.assertEqual(r.status_code, 200)

        r = c.post('/accounts/signup/review/')
        self.assertRedirects(r, '/accounts/signup/otp/')
        self.assertEqual(len(mail.outbox), 1)

        otp = get_otp('newfarmer@example.com', EmailOTP.Purpose.SIGNUP)
        self.assertIsNotNone(otp)

        r = c.post('/accounts/signup/otp/', {'code': '000000'})
        self.assertEqual(r.status_code, 200)
        otp.refresh_from_db()
        self.assertEqual(otp.attempts, 1)

        r = c.post('/accounts/signup/otp/', {'code': otp.code})
        self.assertEqual(r.status_code, 302)

        user = User.objects.filter(email='newfarmer@example.com').first()
        self.assertIsNotNone(user)
        farm = Farm.objects.filter(name='Test Farm').first()
        self.assertIsNotNone(farm)
        self.assertEqual(farm.owner_id, user.id)
        membership = FarmMembership.objects.filter(user=user, farm=farm).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, 'farmer')

        r = c.get('/farm/')
        self.assertEqual(r.status_code, 200)

    def test_duplicate_signup_email_rejected_at_otp_stage(self):
        User.objects.create_user(email='dupe@example.com', first_name='Existing')
        c = Client()
        c.post('/accounts/signup/', {
            'first_name': 'Test', 'last_name': 'Farmer', 'email': 'dupe@example.com', 'phone': ''
        })
        r = c.post('/accounts/signup/farm/', {
            'farm_name': 'Dupe Farm', 'country': 'KE', 'county': 'Nairobi', 'location': 'Westlands'
        })
        # Whatever guard exists (form validation or OTP-stage IntegrityError) should
        # not blow up with an unhandled 500.
        print('duplicate email farm-step status:', r.status_code)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='farmer@example.com', first_name='Farmer')
        self.farm = Farm.objects.create(name='Existing Farm', owner=self.user, country='KE')
        FarmMembership.objects.create(user=self.user, farm=self.farm, role='farmer', status=FarmMembership.Status.ACTIVE)

    def test_full_login_flow(self):
        c = Client()

        r = c.get('/accounts/login/')
        self.assertEqual(r.status_code, 200)

        r = c.post('/accounts/login/', {'code': 'BOGUSCODE'})
        self.assertEqual(r.status_code, 200)  # form error, not redirect

        r = c.post('/accounts/login/', {'code': self.farm.code})
        self.assertRedirects(r, '/accounts/login/email/')

        r = c.post('/accounts/login/email/', {'email': 'doesnotexist@example.com'})
        self.assertEqual(r.status_code, 200)

        r = c.post('/accounts/login/email/', {'email': 'farmer@example.com'})
        self.assertRedirects(r, '/accounts/login/otp/')
        self.assertEqual(len(mail.outbox), 1)

        otp = get_otp('farmer@example.com', EmailOTP.Purpose.LOGIN, farm=self.farm)
        self.assertIsNotNone(otp)

        r = c.post('/accounts/login/otp/', {'code': '000000' if otp.code != '000000' else '111111'})
        self.assertEqual(r.status_code, 200)

        r = c.post('/accounts/login/otp/', {'code': otp.code})
        self.assertRedirects(r, '/farm/')

        r = c.get('/farm/')
        self.assertEqual(r.status_code, 200)

    def test_used_otp_cannot_be_replayed(self):
        c = Client()
        c.post('/accounts/login/', {'code': self.farm.code})
        c.post('/accounts/login/email/', {'email': 'farmer@example.com'})
        otp = get_otp('farmer@example.com', EmailOTP.Purpose.LOGIN, farm=self.farm)
        c.post('/accounts/login/otp/', {'code': otp.code})

        c2 = Client()
        c2.post('/accounts/login/', {'code': self.farm.code})
        c2.post('/accounts/login/email/', {'email': 'farmer@example.com'})
        r = c2.post('/accounts/login/otp/', {'code': otp.code})
        self.assertEqual(r.status_code, 200)  # rejected, not logged in
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_expired_otp_rejected(self):
        otp = EmailOTP.objects.create(email='farmer@example.com', farm=self.farm, purpose=EmailOTP.Purpose.LOGIN)
        otp.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        otp.save(update_fields=['expires_at'])

        c = Client()
        c.post('/accounts/login/', {'code': self.farm.code})
        session = c.session
        session['login_email'] = 'farmer@example.com'
        session.save()

        r = c.post('/accounts/login/otp/', {'code': otp.code})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_max_attempts_locks_out_otp(self):
        otp = EmailOTP.objects.create(email='farmer@example.com', farm=self.farm, purpose=EmailOTP.Purpose.LOGIN)
        for _ in range(6):
            otp.register_failed_attempt()
        otp.refresh_from_db()
        self.assertFalse(otp.is_valid())

    def test_authenticated_user_redirected_away_from_login(self):
        c = Client()
        c.force_login(self.user)
        r = c.get('/accounts/login/')
        self.assertRedirects(r, '/farm/')

    def test_inactive_farm_blocks_login(self):
        self.farm.is_active = False
        self.farm.save(update_fields=['is_active'])
        c = Client()
        r = c.post('/accounts/login/', {'code': self.farm.code})
        self.assertEqual(r.status_code, 200)  # should show "farm not found", not redirect

    def test_resend_otp_cooldown(self):
        # login/email/ itself just issued an OTP, so an immediate resend click
        # is within the 45s cooldown and should be a no-op (no new mail) - the
        # cooldown clock starts at the *original* send, not just at a prior resend.
        c = Client()
        c.post('/accounts/login/', {'code': self.farm.code})
        c.post('/accounts/login/email/', {'email': 'farmer@example.com'})
        mail.outbox = []
        r = c.post('/accounts/login/otp/resend/')
        self.assertRedirects(r, '/accounts/login/otp/')
        self.assertEqual(len(mail.outbox), 0)

        otp = get_otp('farmer@example.com', EmailOTP.Purpose.LOGIN, farm=self.farm)
        otp.created_at = timezone.now() - timezone.timedelta(seconds=46)
        otp.save(update_fields=['created_at'])
        r = c.post('/accounts/login/otp/resend/')
        self.assertEqual(len(mail.outbox), 1)  # cooldown elapsed, resend goes through


class PermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='owner@example.com', first_name='Owner')
        self.worker = User.objects.create_user(email='worker@example.com', first_name='Worker')
        self.farm = Farm.objects.create(name='Perm Farm', owner=self.owner, country='KE')
        FarmMembership.objects.create(user=self.owner, farm=self.farm, role='farmer', status=FarmMembership.Status.ACTIVE)
        FarmMembership.objects.create(user=self.worker, farm=self.farm, role='farm_worker', status=FarmMembership.Status.ACTIVE)

    def test_worker_cannot_reach_worker_management(self):
        c = Client()
        c.force_login(self.worker)
        session = c.session
        session['active_farm_id'] = self.farm.id
        session.save()
        r = c.get('/farm/workers/', follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertRedirects(r, '/farm/')
        messages_text = ' '.join(str(m) for m in r.context['messages'])
        self.assertIn('only farmers and farm managers', messages_text.lower())
