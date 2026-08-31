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
from .models import CreditScoreSnapshot
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
