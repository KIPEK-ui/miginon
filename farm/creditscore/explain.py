"""Exact, closed-form per-feature contributions for the credit score -
mirrors analysis.ml.explain's reasoning: PCA's first component is a linear
combination of the standardized features (score_i = sum(loading_i *
standardized_value_i)), so each feature's exact contribution to PC1 is
loading_i * standardized_value_i, computed directly rather than via a
separate explainability library. The provisional (no-population) method is
a plain mean of already-0-1-oriented features, so its exact contribution is
just each feature's deviation from the neutral midpoint (0.5).

The score itself is a *rank* of PC1 within the peer population, not a
linear function of it - so these contributions explain what drove the
underlying composite up or down, not an exact points breakdown of the
0-100 score (the UI phrasing below is worded to stay honest about that
distinction, matching the "score is relative to your peers" framing
already used elsewhere in this module)."""

FEATURE_LABELS = {
    'farm_age_norm': 'how long the farm has been active',
    'expense_ratio_health': 'expenses staying well below income',
    'income_stability': 'stable month-to-month income',
    'yield_consistency': 'consistent daily milk yield',
    'herd_size_norm': 'herd size',
    'income_category_diversity': 'income source diversity',
    'crop_activity_diversity': 'crop activity diversity',
    'task_on_time_rate': 'completing tasks on time',
    'fiq_balance_norm': 'FIQ token balance earned',
    'fiq_source_diversity': 'diversity of FIQ-earning activity',
}

_NEGLIGIBLE = 0.05


def pca_contributions(loadings, scaled_row, feature_names, sign=1):
    """Exact per-feature contribution to (possibly sign-flipped) PC1 -
    loading_i * standardized_value_i * sign. Sums to PC1 exactly."""
    contributions = []
    for name, loading, value in zip(feature_names, loadings, scaled_row):
        contributions.append({
            'feature': name,
            'label': FEATURE_LABELS.get(name, name),
            'contribution': float(sign * loading * value),
        })
    contributions.sort(key=lambda c: abs(c['contribution']), reverse=True)
    return contributions


def provisional_contributions(imputed, feature_names):
    """Exact per-feature contribution to the provisional composite -
    deviation from the neutral midpoint (0.5). Sums to (mean - 0.5)."""
    contributions = []
    for name in feature_names:
        contributions.append({
            'feature': name,
            'label': FEATURE_LABELS.get(name, name),
            'contribution': float(imputed[name] - 0.5),
        })
    contributions.sort(key=lambda c: abs(c['contribution']), reverse=True)
    return contributions


def plain_language_summary(contributions, top_n=2):
    positive = sorted(
        (c for c in contributions if c['contribution'] > _NEGLIGIBLE),
        key=lambda c: -c['contribution']
    )[:top_n]
    negative = sorted(
        (c for c in contributions if c['contribution'] < -_NEGLIGIBLE),
        key=lambda c: c['contribution']
    )[:top_n]

    parts = []
    if positive:
        parts.append('driven up by ' + ', '.join(c['label'] for c in positive))
    if negative:
        parts.append('held back by ' + ', '.join(c['label'] for c in negative))
    return '; '.join(parts) if parts else "close to a typical peer farm on every factor"
