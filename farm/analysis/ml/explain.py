"""Exact, closed-form per-feature contribution for a Ridge prediction.

This is mathematically what SHAP's own LinearExplainer reduces to for a
linear model (contribution_i = coefficient_i * standardized_value_i, and
intercept + sum(contributions) = the prediction exactly) - computed
directly rather than via the shap library. See the project plan's
dependency spike: shap pulls in numba/llvmlite/pandas, which doesn't fit
Vercel's Python function size limit. A linear model's own coefficients are
already exact, not approximated, so nothing is lost by not using shap here."""

FEATURE_LABELS = {
    'days_in_milk': 'days since calving',
    'dairy_meal_kg': 'dairy meal fed',
    'silage_hay_kg': 'silage/hay fed',
    'rolling_avg_liters_7d': 'recent average yield',
    'is_heifer': 'being a heifer',
}


def explain_prediction(trained_model, x_scaled):
    """Returns a list of {feature, label, contribution} sorted by
    |contribution| descending."""
    contributions = []
    for name, coef, value in zip(trained_model.feature_names, trained_model.model.coef_, x_scaled):
        contributions.append({
            'feature': name,
            'label': FEATURE_LABELS.get(name, name),
            'contribution': float(coef * value),
        })
    contributions.sort(key=lambda c: abs(c['contribution']), reverse=True)
    return contributions


def plain_language_summary(contributions, top_n=2):
    parts = []
    for c in contributions[:top_n]:
        if abs(c['contribution']) < 0.05:
            continue
        sign = '+' if c['contribution'] >= 0 else ''
        parts.append(f"{sign}{c['contribution']:.1f}L from {c['label']}")
    return ', '.join(parts) if parts else 'close to this cow\'s recent average'
