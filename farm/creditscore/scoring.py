"""Population-relative credit scoring via PCA + KMeans - no historical
labeled loan outcomes exist to train a supervised classifier on, so this
scores farms relative to their real peers instead (see the module's
project plan). StandardScaler before fitting and a fixed random_state on
both PCA and KMeans mirror analysis.ml.train's house style, and matter
more here than there: without a fixed seed, recomputing an unchanged
population could reorder tiers or jitter scores purely from restart
noise, which would also defeat creditscore.services' hash-diff gate."""

import numpy as np
from django.utils import timezone
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .explain import pca_contributions, plain_language_summary, provisional_contributions
from .features import FEATURE_NAMES, build_farm_raw_features, build_population_matrix
from .models import CreditScoreSnapshot

MIN_POPULATION_FARMS = 8
SMALL_POPULATION_K_THRESHOLD = 12
RANDOM_STATE = 42

CATEGORY_FEATURES = {
    'tenure': ['farm_age_norm'],
    'financial': ['expense_ratio_health', 'income_stability'],
    'production': ['yield_consistency', 'herd_size_norm'],
    'diversification': ['income_category_diversity', 'crop_activity_diversity'],
    'behavioral': ['task_on_time_rate'],
    'blockchain': ['fiq_balance_norm', 'fiq_source_diversity'],
}

TIER_LABELS_BY_K = {
    2: [CreditScoreSnapshot.Tier.FAIR, CreditScoreSnapshot.Tier.GOOD],
    4: [CreditScoreSnapshot.Tier.POOR, CreditScoreSnapshot.Tier.FAIR,
        CreditScoreSnapshot.Tier.GOOD, CreditScoreSnapshot.Tier.EXCELLENT],
}


def _category_breakdown(feature_row, feature_names):
    """0-100 per-domain sub-scores from this farm's own (imputed) feature
    values - a simple within-domain average, not population-relative, so
    it's interpretable without explaining PCA loadings to a farmer."""
    value_by_name = dict(zip(feature_names, feature_row))
    return {
        category: round(float(np.mean([value_by_name[name] for name in names])) * 100, 1)
        for category, names in CATEGORY_FEATURES.items()
    }


def _provisional_tier(score):
    if score < 40:
        return CreditScoreSnapshot.Tier.POOR
    if score < 60:
        return CreditScoreSnapshot.Tier.FAIR
    if score < 80:
        return CreditScoreSnapshot.Tier.GOOD
    return CreditScoreSnapshot.Tier.EXCELLENT


def compute_provisional_score(farm, as_of=None):
    """No peer population to rank against (either the platform-wide
    population is below MIN_POPULATION_FARMS, or the caller wants a single
    farm's score in isolation) - a deterministic weighted-average composite
    instead of clustering. method='provisional', population_size=1."""
    as_of = as_of or timezone.now().date()
    raw = build_farm_raw_features(farm, as_of)
    imputed = {name: (raw[name] if raw[name] is not None else 0.5) for name in FEATURE_NAMES}
    composite = float(np.mean([imputed[name] for name in FEATURE_NAMES]))
    score = int(round(composite * 100))
    contributions = provisional_contributions(imputed, FEATURE_NAMES)
    return {
        'score': score,
        'tier': _provisional_tier(score),
        'category_breakdown': _category_breakdown([imputed[name] for name in FEATURE_NAMES], FEATURE_NAMES),
        'feature_values': imputed,
        'population_size': 1,
        'method': CreditScoreSnapshot.Method.PROVISIONAL,
        'contributions': contributions,
        'explanation': plain_language_summary(contributions),
    }


def compute_population_scores(as_of=None):
    """farm_id -> {score, tier, category_breakdown, feature_values,
    population_size, method}. Below MIN_POPULATION_FARMS, every eligible
    farm falls back to compute_provisional_score instead - PCA/KMeans on
    too few points would just fit noise."""
    as_of = as_of or timezone.now().date()
    farms, matrix, feature_names = build_population_matrix(as_of)

    if len(farms) < MIN_POPULATION_FARMS:
        return {farm.id: compute_provisional_score(farm, as_of) for farm in farms}

    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)

    pca = PCA(n_components=1, random_state=RANDOM_STATE)
    pc1 = pca.fit_transform(scaled)[:, 0]

    # PCA's sign is arbitrary - orient it so higher PC1 always means a
    # healthier farm, using the plain per-farm feature average (every
    # feature is already scaled 0-1, higher = healthier) as the reference.
    # The same sign is applied to the loadings below so per-feature
    # contributions stay consistent with the (possibly flipped) score.
    sign = 1
    raw_composite = matrix.mean(axis=1)
    if np.corrcoef(pc1, raw_composite)[0, 1] < 0:
        pc1 = -pc1
        sign = -1
    loadings = pca.components_[0]

    # Percentile rank via plain argsort (twice), not scipy.stats, matching
    # this codebase's no-scipy-calls convention.
    order = np.argsort(pc1)
    ranks = np.empty_like(order)
    ranks[order] = np.arange(len(pc1))
    percentiles = ranks / max(len(pc1) - 1, 1) * 100

    k = 4 if len(farms) >= SMALL_POPULATION_K_THRESHOLD else 2
    kmeans = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    cluster_labels = kmeans.fit_predict(scaled)

    # Tiers are data-driven, not fixed percentile cutoffs: rank each
    # cluster by its members' mean PC1, then assign tier labels in that
    # order (ascending) - PCA drives the continuous score, KMeans drives
    # the tier boundaries.
    cluster_pc1_means = {c: pc1[cluster_labels == c].mean() for c in range(k)}
    cluster_rank_order = sorted(cluster_pc1_means, key=cluster_pc1_means.get)
    tier_labels = TIER_LABELS_BY_K[k]
    tier_by_cluster = {cluster: tier_labels[rank] for rank, cluster in enumerate(cluster_rank_order)}

    results = {}
    for i, farm in enumerate(farms):
        contributions = pca_contributions(loadings, scaled[i], feature_names, sign=sign)
        results[farm.id] = {
            'score': int(round(percentiles[i])),
            'tier': tier_by_cluster[cluster_labels[i]],
            'category_breakdown': _category_breakdown(matrix[i], feature_names),
            'feature_values': {name: float(matrix[i][j]) for j, name in enumerate(feature_names)},
            'population_size': len(farms),
            'method': CreditScoreSnapshot.Method.POPULATION,
            'contributions': contributions,
            'explanation': plain_language_summary(contributions),
        }
    return results
