from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from blockchain.models import FiqLedgerEntry
from cows.models import Cow, MilkRecord, Session
from farms.models import Block, Farm, FarmMembership, FarmRole
from finance.models import Transaction
from tasks.models import Task

from .explain import plain_language_summary
from .features import build_farm_raw_features
from .models import CreditScoreSnapshot, DataPartner, DataShareConsent
from .scoring import MIN_POPULATION_FARMS, compute_population_scores, compute_provisional_score
from .services import recompute_farm_score
from .views import _contributions_display

_TIER_RANK = {
    CreditScoreSnapshot.Tier.POOR: 0, CreditScoreSnapshot.Tier.FAIR: 1,
    CreditScoreSnapshot.Tier.GOOD: 2, CreditScoreSnapshot.Tier.EXCELLENT: 3,
}


def _old_farm(name, days_old=150):
    user = User.objects.create_user(email=f'{name.lower().replace(" ", "_")}@example.com', first_name='Test')
    farm = Farm.objects.create(name=name, owner=user)
    Farm.objects.filter(id=farm.id).update(created_at=timezone.now() - timedelta(days=days_old))
    farm.refresh_from_db()
    FarmMembership.objects.create(farm=farm, user=user, role=FarmRole.FARMER)
    return farm, user


def _seed_quality(farm, quality, today):
    """quality: 0.0 (worst) to 1.0 (best), driving every domain consistently
    so the resulting composite has a real, controllable spread - mirrors the
    live smoke test used to verify this module against real Hedera testnet
    data during development."""
    block = Block.objects.create(farm=farm, name=f'{farm.name} Block')
    cow = Cow.objects.create(farm=farm, tag_id=f'{farm.name}-1', breed='Friesian', status=Cow.Status.ACTIVE, block=block)

    base = 10.0
    spread = (1 - quality) * 8
    records = []
    for d in range(10):
        wobble = spread * (1 if d % 2 == 0 else -1) * 0.5
        liters = max(base + wobble, 0.5)
        records.append(MilkRecord(
            farm=farm, cow=cow, block=block, date=today - timedelta(days=10 - d),
            session=Session.AM, liters=Decimal(str(round(liters, 2))),
        ))
    MilkRecord.objects.bulk_create(records)

    expense = Decimal(str(int(100 + (1 - quality) * 800)))
    Transaction.objects.create(farm=farm, kind=Transaction.Kind.INCOME, category=Transaction.Category.SALES, date=today, amount=Decimal('1000'))
    Transaction.objects.create(farm=farm, kind=Transaction.Kind.EXPENSE, category=Transaction.Category.FEED, date=today, amount=expense)

    completed_offset = 0 if quality > 0.5 else 3
    Task.objects.create(
        farm=farm, title=f'{farm.name} task', status=Task.Status.DONE,
        due_date=today - timedelta(days=5), completed_at=timezone.now() - timedelta(days=5 - completed_offset),
    )

    FiqLedgerEntry.objects.create(farm=farm, amount=Decimal(str(int(quality * 100))), reason=FiqLedgerEntry.Reason.COW_REGISTERED, cow=cow)


class FeatureEngineeringTests(TestCase):
    def test_single_farm_features_match_expected_values(self):
        farm, _user = _old_farm('Feature Farm', days_old=200)
        today = timezone.now().date()
        block = Block.objects.create(farm=farm, name='Block')
        cow = Cow.objects.create(farm=farm, tag_id='F-001', breed='Friesian', status=Cow.Status.ACTIVE, block=block)

        for i in range(10):
            MilkRecord.objects.create(
                farm=farm, cow=cow, block=block, date=today - timedelta(days=10 - i),
                session=Session.AM, liters=Decimal('10.0'),
            )
        Transaction.objects.create(farm=farm, kind=Transaction.Kind.INCOME, category=Transaction.Category.SALES, date=today, amount=Decimal('1000'))
        Transaction.objects.create(farm=farm, kind=Transaction.Kind.EXPENSE, category=Transaction.Category.FEED, date=today, amount=Decimal('300'))
        Task.objects.create(
            farm=farm, title='On time', status=Task.Status.DONE,
            due_date=today - timedelta(days=5), completed_at=timezone.now() - timedelta(days=6),
        )
        FiqLedgerEntry.objects.create(farm=farm, amount=Decimal('20'), reason=FiqLedgerEntry.Reason.COW_REGISTERED, cow=cow)

        feats = build_farm_raw_features(farm, as_of=today)
        self.assertAlmostEqual(feats['farm_age_norm'], 200 / 1095)
        self.assertAlmostEqual(feats['expense_ratio_health'], 0.7)
        self.assertIsNone(feats['income_stability'])  # only one month of income data
        self.assertAlmostEqual(feats['yield_consistency'], 1.0)  # constant liters -> zero CV
        self.assertAlmostEqual(feats['herd_size_norm'], 1 / 50)
        self.assertAlmostEqual(feats['income_category_diversity'], 2 / 9)
        self.assertEqual(feats['crop_activity_diversity'], 0.0)
        self.assertAlmostEqual(feats['task_on_time_rate'], 1.0)
        self.assertAlmostEqual(feats['fiq_balance_norm'], 20 / 500)
        self.assertAlmostEqual(feats['fiq_source_diversity'], 1 / 3)

    def test_crop_only_farm_imputes_production_as_none_without_crashing(self):
        farm, _user = _old_farm('Crop Only Farm', days_old=100)
        feats = build_farm_raw_features(farm)
        self.assertIsNone(feats['yield_consistency'])
        self.assertIsNone(feats['herd_size_norm'])
        # Every other feature still resolves to a plain number, not None.
        for name in ('farm_age_norm', 'expense_ratio_health', 'income_category_diversity',
                     'crop_activity_diversity', 'task_on_time_rate', 'fiq_balance_norm', 'fiq_source_diversity'):
            self.assertIsNotNone(feats[name])


class PopulationScoringTests(TestCase):
    def test_below_minimum_population_falls_back_to_provisional(self):
        today = timezone.now().date()
        for i, quality in enumerate([0.1, 0.3, 0.5, 0.7]):
            farm, _user = _old_farm(f'Small Pop Farm {i}')
            _seed_quality(farm, quality, today)

        scores = compute_population_scores(as_of=today)
        self.assertEqual(len(scores), 4)
        self.assertLess(len(scores), MIN_POPULATION_FARMS)
        for result in scores.values():
            self.assertEqual(result['method'], CreditScoreSnapshot.Method.PROVISIONAL)
            self.assertEqual(result['population_size'], 1)

    def test_population_scores_are_deterministic_and_tier_monotonic(self):
        today = timezone.now().date()
        qualities = [0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 0.95]  # exactly MIN_POPULATION_FARMS
        farms = []
        for i, quality in enumerate(qualities):
            farm, _user = _old_farm(f'Pop Farm {i}')
            _seed_quality(farm, quality, today)
            farms.append((farm, quality))

        scores_a = compute_population_scores(as_of=today)
        scores_b = compute_population_scores(as_of=today)

        self.assertEqual(len(scores_a), len(qualities))
        for result in scores_a.values():
            self.assertEqual(result['method'], CreditScoreSnapshot.Method.POPULATION)
            self.assertEqual(result['population_size'], len(qualities))

        for farm, _quality in farms:
            self.assertEqual(scores_a[farm.id]['score'], scores_b[farm.id]['score'])
            self.assertEqual(scores_a[farm.id]['tier'], scores_b[farm.id]['tier'])

        by_tier = {}
        for farm, quality in farms:
            by_tier.setdefault(scores_a[farm.id]['tier'], []).append(quality)
        tier_means = {t: sum(v) / len(v) for t, v in by_tier.items()}
        ordered = sorted(tier_means, key=lambda t: _TIER_RANK[t])
        means = [tier_means[t] for t in ordered]
        self.assertEqual(means, sorted(means))


class ExplainabilityTests(TestCase):
    """The credit score is PCA + KMeans, not a black box - every contribution
    reported here must be an EXACT decomposition (loading * standardized
    value, or deviation from the neutral midpoint), not an approximation,
    matching analysis.ml.explain's contract for the milk-yield model."""

    def test_provisional_contributions_sum_to_composite_minus_half(self):
        today = timezone.now().date()
        farm, _user = _old_farm('Explain Provisional Farm')
        _seed_quality(farm, 0.7, today)

        result = compute_provisional_score(farm, as_of=today)
        total_contribution = sum(c['contribution'] for c in result['contributions'])
        # Each contribution is (imputed_i - 0.5) exactly - cross-check against
        # an independently recomputed imputed feature set, not the rounded
        # display score (int(round(...)) would introduce its own slack here).
        raw = build_farm_raw_features(farm, as_of=today)
        imputed = {name: (raw[name] if raw[name] is not None else 0.5) for name in result['feature_values']}
        expected_total = sum(v - 0.5 for v in imputed.values())
        self.assertAlmostEqual(total_contribution, expected_total, places=6)
        self.assertTrue(result['explanation'])
        self.assertEqual(len(result['contributions']), len(result['feature_values']))

    def test_population_contributions_sum_exactly_to_pc1(self):
        """Cross-checks against an independent PCA run (not the production
        code path) that each farm's contributions really do add up to its
        (sign-oriented) PC1 value - proving the "exact, not approximated"
        claim in creditscore.explain's docstring, not just trusting it."""
        import numpy as np
        from sklearn.decomposition import PCA as SKPCA
        from sklearn.preprocessing import StandardScaler as SKScaler

        from .features import build_population_matrix
        from .scoring import RANDOM_STATE

        today = timezone.now().date()
        qualities = [0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 0.95]
        farms = []
        for i, quality in enumerate(qualities):
            farm, _user = _old_farm(f'Explain Pop Farm {i}')
            _seed_quality(farm, quality, today)
            farms.append(farm)

        scores = compute_population_scores(as_of=today)

        ordered_farms, matrix, _names = build_population_matrix(as_of=today)
        scaled = SKScaler().fit_transform(matrix)
        pc1 = SKPCA(n_components=1, random_state=RANDOM_STATE).fit_transform(scaled)[:, 0]
        raw_composite = matrix.mean(axis=1)
        if np.corrcoef(pc1, raw_composite)[0, 1] < 0:
            pc1 = -pc1

        for i, farm in enumerate(ordered_farms):
            result = scores[farm.id]
            self.assertTrue(result['contributions'])
            self.assertTrue(result['explanation'])
            total_contribution = sum(c['contribution'] for c in result['contributions'])
            self.assertAlmostEqual(total_contribution, pc1[i], places=6)
            magnitudes = [abs(c['contribution']) for c in result['contributions']]
            self.assertEqual(magnitudes, sorted(magnitudes, reverse=True))

    def test_plain_language_summary_names_biggest_positive_and_negative_drivers(self):
        contributions = [
            {'feature': 'a', 'label': 'factor a', 'contribution': 1.5},
            {'feature': 'b', 'label': 'factor b', 'contribution': -1.2},
            {'feature': 'c', 'label': 'factor c', 'contribution': 0.01},  # below the negligible threshold
        ]
        summary = plain_language_summary(contributions)
        self.assertIn('factor a', summary)
        self.assertIn('factor b', summary)
        self.assertNotIn('factor c', summary)

    def test_contributions_display_normalizes_to_plus_minus_100(self):
        contributions = [
            {'feature': 'a', 'label': 'factor a', 'contribution': 2.0},
            {'feature': 'b', 'label': 'factor b', 'contribution': -1.0},
        ]
        display = _contributions_display(contributions)
        self.assertEqual(display[0]['impact'], 100)
        self.assertEqual(display[1]['impact'], -50)

    def test_contributions_display_handles_empty_list(self):
        self.assertEqual(_contributions_display([]), [])


class RecomputeServiceTests(TestCase):
    @patch('creditscore.services.anchor_hash')
    def test_recompute_creates_one_snapshot_and_hash_diff_gate_prevents_duplicates(self, mock_anchor):
        mock_anchor.return_value = {'topic_id': '0.0.999', 'sequence_number': 1, 'consensus_timestamp': '1.1'}
        farm, user = _old_farm('Recompute Farm')
        _seed_quality(farm, 0.6, timezone.now().date())

        snapshot_1 = recompute_farm_score(farm, user=user)
        self.assertEqual(CreditScoreSnapshot.objects.filter(farm=farm).count(), 1)
        self.assertTrue(snapshot_1.hedera_anchored_at)
        self.assertEqual(snapshot_1.hedera_topic_id, '0.0.999')
        self.assertTrue(snapshot_1.explanation)
        self.assertTrue(snapshot_1.contributions)

        snapshot_2 = recompute_farm_score(farm, user=user)
        self.assertEqual(CreditScoreSnapshot.objects.filter(farm=farm).count(), 1)
        self.assertEqual(snapshot_1.id, snapshot_2.id)
        mock_anchor.assert_called_once()

    @patch('creditscore.services.anchor_hash')
    def test_recompute_survives_hedera_being_unavailable(self, mock_anchor):
        mock_anchor.return_value = None
        farm, user = _old_farm('Offline Recompute Farm')
        _seed_quality(farm, 0.4, timezone.now().date())

        snapshot = recompute_farm_score(farm, user=user)
        self.assertIsNotNone(snapshot.id)
        self.assertFalse(snapshot.hedera_anchored_at)


class RecomputeViewPermissionTests(TestCase):
    def setUp(self):
        self.farm, self.farmer = _old_farm('Permission Farm')
        _seed_quality(self.farm, 0.5, timezone.now().date())
        self.worker = User.objects.create_user(email='cs_worker@example.com', first_name='Worker')
        FarmMembership.objects.create(farm=self.farm, user=self.worker, role=FarmRole.WORKER)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    @patch('creditscore.services.anchor_hash')
    def test_worker_cannot_recompute(self, mock_anchor):
        self._login(self.worker)
        self.client.post('/credit-score/recompute/')
        self.assertEqual(CreditScoreSnapshot.objects.filter(farm=self.farm).count(), 0)
        mock_anchor.assert_not_called()

    @patch('creditscore.services.anchor_hash')
    def test_farmer_can_recompute(self, mock_anchor):
        mock_anchor.return_value = None
        self._login(self.farmer)
        response = self.client.post('/credit-score/recompute/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CreditScoreSnapshot.objects.filter(farm=self.farm).count(), 1)


class DataPartnerApiTests(TestCase):
    """Covers the read-only partner API (creditscore.api.farm_score) - the
    first concrete piece of the data-marketplace model: a partner can only
    ever see a score for a farm that has actively consented to share with
    it, and a missing key, a farm that exists without consent, and a farm
    that doesn't exist at all must all look identical from the outside."""

    def setUp(self):
        self.farm, self.farmer = _old_farm('Api Farm')
        _seed_quality(self.farm, 0.6, timezone.now().date())
        self.partner = DataPartner.objects.create(
            name='Test SACCO', slug='test-sacco', status=DataPartner.Status.APPROVED
        )

    def _url(self, farm_id=None):
        return f'/credit-score/api/farms/{farm_id if farm_id is not None else self.farm.id}/score/'

    def test_missing_api_key_is_rejected(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_invalid_api_key_is_rejected(self):
        response = self.client.get(self._url(), HTTP_X_API_KEY='not-a-real-key')
        self.assertEqual(response.status_code, 401)

    def test_pending_partner_key_is_rejected(self):
        self.partner.status = DataPartner.Status.PENDING
        self.partner.save(update_fields=['status'])
        response = self.client.get(self._url(), HTTP_X_API_KEY=self.partner.api_key)
        self.assertEqual(response.status_code, 401)

    def test_suspended_partner_key_is_rejected(self):
        self.partner.status = DataPartner.Status.SUSPENDED
        self.partner.save(update_fields=['status'])
        response = self.client.get(self._url(), HTTP_X_API_KEY=self.partner.api_key)
        self.assertEqual(response.status_code, 401)

    def test_valid_key_without_consent_returns_404_same_as_missing_farm(self):
        with_consent_response_shape = self.client.get(self._url(farm_id=999999), HTTP_X_API_KEY=self.partner.api_key)
        without_consent_response = self.client.get(self._url(), HTTP_X_API_KEY=self.partner.api_key)
        self.assertEqual(with_consent_response_shape.status_code, 404)
        self.assertEqual(without_consent_response.status_code, 404)
        self.assertEqual(with_consent_response_shape.json(), without_consent_response.json())

    @patch('creditscore.services.anchor_hash')
    def test_consented_farm_returns_score_with_verification_fields(self, mock_anchor):
        mock_anchor.return_value = {'topic_id': '0.0.999', 'sequence_number': 7, 'consensus_timestamp': '1.1'}
        recompute_farm_score(self.farm, user=self.farmer)
        DataShareConsent.objects.create(farm=self.farm, partner=self.partner, granted_by=self.farmer)

        response = self.client.get(self._url(), HTTP_X_API_KEY=self.partner.api_key)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['farm_id'], self.farm.id)
        self.assertIn('score', body)
        self.assertEqual(body['verification']['hedera_topic_id'], '0.0.999')
        self.assertEqual(body['verification']['hedera_sequence_number'], 7)

    @patch('creditscore.services.anchor_hash')
    def test_revoked_consent_blocks_access_again(self, mock_anchor):
        mock_anchor.return_value = None
        recompute_farm_score(self.farm, user=self.farmer)
        consent = DataShareConsent.objects.create(farm=self.farm, partner=self.partner, granted_by=self.farmer)

        self.assertEqual(self.client.get(self._url(), HTTP_X_API_KEY=self.partner.api_key).status_code, 200)

        consent.revoked_at = timezone.now()
        consent.save(update_fields=['revoked_at'])
        self.assertEqual(self.client.get(self._url(), HTTP_X_API_KEY=self.partner.api_key).status_code, 404)

    def test_consented_farm_without_a_computed_score_yet_returns_404(self):
        DataShareConsent.objects.create(farm=self.farm, partner=self.partner, granted_by=self.farmer)
        response = self.client.get(self._url(), HTTP_X_API_KEY=self.partner.api_key)
        self.assertEqual(response.status_code, 404)


class DataSharingConsentViewTests(TestCase):
    """The farmer-facing half of the data-partner flow: granting/revoking
    is scoped to the same manage-tier as recompute (see RecomputeViewPermissionTests
    above), only ever touches consent for the requester's own active farm,
    and re-granting after a revoke reactivates the same row rather than
    erroring on the (farm, partner) unique constraint."""

    def setUp(self):
        self.farm, self.farmer = _old_farm('Sharing Farm')
        self.worker = User.objects.create_user(email='sharing_worker@example.com', first_name='Worker')
        FarmMembership.objects.create(farm=self.farm, user=self.worker, role=FarmRole.WORKER)
        self.partner = DataPartner.objects.create(
            name='Sharing SACCO', slug='sharing-sacco', status=DataPartner.Status.APPROVED
        )
        self.pending_partner = DataPartner.objects.create(name='Pending SACCO', slug='pending-sacco')

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_page_lists_only_approved_partners(self):
        self._login(self.farmer)
        response = self.client.get('/credit-score/data-sharing/')
        self.assertContains(response, 'Sharing SACCO')
        self.assertNotContains(response, 'Pending SACCO')

    def test_farmer_can_grant_and_revoke(self):
        self._login(self.farmer)
        self.client.post(f'/credit-score/data-sharing/{self.partner.id}/grant/')
        consent = DataShareConsent.objects.get(farm=self.farm, partner=self.partner)
        self.assertTrue(consent.is_active)
        self.assertEqual(consent.granted_by, self.farmer)

        self.client.post(f'/credit-score/data-sharing/{self.partner.id}/revoke/')
        consent.refresh_from_db()
        self.assertFalse(consent.is_active)

    def test_regranting_after_revoke_reactivates_the_same_row(self):
        self._login(self.farmer)
        self.client.post(f'/credit-score/data-sharing/{self.partner.id}/grant/')
        self.client.post(f'/credit-score/data-sharing/{self.partner.id}/revoke/')
        self.client.post(f'/credit-score/data-sharing/{self.partner.id}/grant/')

        self.assertEqual(DataShareConsent.objects.filter(farm=self.farm, partner=self.partner).count(), 1)
        self.assertTrue(DataShareConsent.objects.get(farm=self.farm, partner=self.partner).is_active)

    def test_cannot_grant_a_pending_partner(self):
        self._login(self.farmer)
        response = self.client.post(f'/credit-score/data-sharing/{self.pending_partner.id}/grant/')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(DataShareConsent.objects.filter(partner=self.pending_partner).exists())

    def test_worker_cannot_grant(self):
        self._login(self.worker)
        self.client.post(f'/credit-score/data-sharing/{self.partner.id}/grant/')
        self.assertFalse(DataShareConsent.objects.filter(farm=self.farm, partner=self.partner).exists())


class PartnerApplicationTests(TestCase):
    """The self-serve half: anyone can apply, but an application alone
    never grants API access - see DataPartner's docstring."""

    def test_valid_application_creates_a_pending_partner(self):
        response = self.client.post('/credit-score/partners/apply/', {
            'name': 'New Lender Co', 'contact_name': 'Jane Doe', 'contact_email': 'jane@newlender.example',
        })
        self.assertEqual(response.status_code, 200)
        partner = DataPartner.objects.get(name='New Lender Co')
        self.assertEqual(partner.status, DataPartner.Status.PENDING)
        self.assertTrue(partner.slug)
        self.assertTrue(partner.api_key)

    def test_pending_partner_from_application_cannot_use_the_api_yet(self):
        self.client.post('/credit-score/partners/apply/', {
            'name': 'Another Lender', 'contact_name': 'John Doe', 'contact_email': 'john@anotherlender.example',
        })
        partner = DataPartner.objects.get(name='Another Lender')
        farm, _user = _old_farm('Applicant Test Farm')
        response = self.client.get(f'/credit-score/api/farms/{farm.id}/score/', HTTP_X_API_KEY=partner.api_key)
        self.assertEqual(response.status_code, 401)

    def test_missing_email_is_rejected(self):
        response = self.client.post('/credit-score/partners/apply/', {'name': 'No Email Co', 'contact_name': 'X'})
        self.assertEqual(response.status_code, 200)  # re-renders the form with errors
        self.assertFalse(DataPartner.objects.filter(name='No Email Co').exists())
