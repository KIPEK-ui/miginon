import json
from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from farms.models import Farm, FarmMembership, FarmRole

from .models import Notification, PushSubscription
from .services import notify


class NotifyDispatchTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(email='actor@example.com', first_name='Ana')
        self.farm = Farm.objects.create(name='Notify Farm', owner=self.actor)

    def test_no_recipient_always_logs_in_app(self):
        notification = notify(self.farm, self.actor, Notification.Verb.CREATED, 'cow', 'C-001')
        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.filter(farm=self.farm).count(), 1)

    @patch('notifications.push.send_push_to_user')
    def test_recipient_with_in_app_only_logs_but_does_not_push(self, mock_push):
        recipient = User.objects.create_user(
            email='inapp@example.com', first_name='In',
            notification_delivery=User.NotificationDelivery.IN_APP,
        )
        notification = notify(
            self.farm, self.actor, Notification.Verb.CREATED, 'task', 'Deworm cows', recipient=recipient
        )
        self.assertIsNotNone(notification)
        mock_push.assert_not_called()

    @patch('notifications.push.send_push_to_user')
    def test_recipient_with_push_only_pushes_but_does_not_log(self, mock_push):
        recipient = User.objects.create_user(
            email='push@example.com', first_name='Pu',
            notification_delivery=User.NotificationDelivery.PUSH,
        )
        notification = notify(
            self.farm, self.actor, Notification.Verb.CREATED, 'task', 'Deworm cows', recipient=recipient
        )
        self.assertIsNone(notification)
        self.assertFalse(Notification.objects.filter(farm=self.farm, recipient=recipient).exists())
        mock_push.assert_called_once()

    @patch('notifications.push.send_push_to_user')
    def test_recipient_with_both_logs_and_pushes(self, mock_push):
        recipient = User.objects.create_user(
            email='both@example.com', first_name='Bo',
            notification_delivery=User.NotificationDelivery.BOTH,
        )
        notification = notify(
            self.farm, self.actor, Notification.Verb.CREATED, 'task', 'Deworm cows', recipient=recipient
        )
        self.assertIsNotNone(notification)
        mock_push.assert_called_once()

    @patch('notifications.whatsapp.send_whatsapp_message')
    def test_whatsapp_sent_when_recipient_opted_in_with_a_number(self, mock_whatsapp):
        recipient = User.objects.create_user(
            email='wa@example.com', first_name='Wa',
            notification_delivery=User.NotificationDelivery.IN_APP,
            whatsapp_notifications_enabled=True, whatsapp_number='+254700000000',
        )
        notify(self.farm, self.actor, Notification.Verb.CREATED, 'task', 'Deworm cows', recipient=recipient)
        mock_whatsapp.assert_called_once()
        self.assertEqual(mock_whatsapp.call_args.args[0], '+254700000000')

    @patch('notifications.whatsapp.send_whatsapp_message')
    def test_whatsapp_not_sent_when_disabled(self, mock_whatsapp):
        recipient = User.objects.create_user(
            email='nowa@example.com', first_name='No',
            whatsapp_notifications_enabled=False, whatsapp_number='+254700000000',
        )
        notify(self.farm, self.actor, Notification.Verb.CREATED, 'task', 'Deworm cows', recipient=recipient)
        mock_whatsapp.assert_not_called()

    @patch('notifications.whatsapp.send_whatsapp_message')
    def test_whatsapp_not_sent_without_a_number(self, mock_whatsapp):
        recipient = User.objects.create_user(
            email='nonum@example.com', first_name='No',
            whatsapp_notifications_enabled=True, whatsapp_number='',
        )
        notify(self.farm, self.actor, Notification.Verb.CREATED, 'task', 'Deworm cows', recipient=recipient)
        mock_whatsapp.assert_not_called()

    @patch('notifications.whatsapp.send_whatsapp_message')
    def test_whatsapp_not_sent_for_untargeted_activity_logging(self, mock_whatsapp):
        notify(self.farm, self.actor, Notification.Verb.CREATED, 'cow', 'C-001')
        mock_whatsapp.assert_not_called()


class SendWhatsappMessageTests(TestCase):
    @patch('notifications.whatsapp.requests.post')
    def test_sends_expected_payload_and_auth_header(self, mock_post):
        from django.test import override_settings

        mock_post.return_value.ok = True
        with override_settings(WHATSAPP_ACCESS_TOKEN='tok123', WHATSAPP_PHONE_NUMBER_ID='pn456', WHATSAPP_API_VERSION='v20.0'):
            from .whatsapp import send_whatsapp_message
            send_whatsapp_message('+254700000000', 'Hello farmer')

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn('pn456', args[0])
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer tok123')
        self.assertEqual(kwargs['json']['to'], '+254700000000')
        self.assertEqual(kwargs['json']['text']['body'], 'Hello farmer')

    @patch('notifications.whatsapp.requests.post')
    def test_does_nothing_when_not_configured(self, mock_post):
        from django.test import override_settings

        with override_settings(WHATSAPP_ACCESS_TOKEN='', WHATSAPP_PHONE_NUMBER_ID=''):
            from .whatsapp import send_whatsapp_message
            send_whatsapp_message('+254700000000', 'Hello farmer')
        mock_post.assert_not_called()

    def test_request_failure_is_swallowed(self):
        import requests
        from django.test import override_settings

        with patch('notifications.whatsapp.requests.post', side_effect=requests.RequestException('network down')):
            with override_settings(WHATSAPP_ACCESS_TOKEN='tok', WHATSAPP_PHONE_NUMBER_ID='pn'):
                from .whatsapp import send_whatsapp_message
                send_whatsapp_message('+254700000000', 'Hello farmer')  # must not raise


class PushSubscribeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.farm = Farm.objects.create(name='Notify Farm', owner=self.user)
        FarmMembership.objects.create(user=self.user, farm=self.farm, role=FarmRole.FARMER)
        self.client.force_login(self.user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_valid_payload_creates_subscription(self):
        response = self.client.post(
            '/notifications/push/subscribe/',
            data=json.dumps({
                'endpoint': 'https://push.example.com/abc',
                'keys': {'p256dh': 'pkey', 'auth': 'akey'},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(user=self.user, endpoint='https://push.example.com/abc').exists())

    def test_resubscribing_the_same_endpoint_updates_rather_than_duplicates(self):
        PushSubscription.objects.create(
            user=self.user, endpoint='https://push.example.com/abc', p256dh='old', auth='old',
        )
        self.client.post(
            '/notifications/push/subscribe/',
            data=json.dumps({
                'endpoint': 'https://push.example.com/abc',
                'keys': {'p256dh': 'new', 'auth': 'new'},
            }),
            content_type='application/json',
        )
        self.assertEqual(PushSubscription.objects.filter(endpoint='https://push.example.com/abc').count(), 1)
        sub = PushSubscription.objects.get(endpoint='https://push.example.com/abc')
        self.assertEqual(sub.p256dh, 'new')

    def test_invalid_payload_returns_400(self):
        response = self.client.post(
            '/notifications/push/subscribe/', data=json.dumps({'endpoint': 'x'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class NotificationListViewTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.worker = User.objects.create_user(email='worker@example.com', first_name='Wes')
        self.farm = Farm.objects.create(name='Notify Farm', owner=self.farmer)
        FarmMembership.objects.create(user=self.farmer, farm=self.farm, role=FarmRole.FARMER)
        FarmMembership.objects.create(user=self.worker, farm=self.farm, role=FarmRole.WORKER)

        notify(self.farm, self.farmer, Notification.Verb.CREATED, 'cow', 'by farmer')
        notify(self.farm, self.worker, Notification.Verb.CREATED, 'cow', 'by worker')

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_farmer_sees_the_whole_activity_feed(self):
        self._login(self.farmer)
        response = self.client.get('/notifications/')
        self.assertEqual(len(response.context['notifications']), 2)

    def test_worker_sees_only_their_own_actions(self):
        self._login(self.worker)
        response = self.client.get('/notifications/')
        notifications = response.context['notifications']
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].actor, self.worker)
