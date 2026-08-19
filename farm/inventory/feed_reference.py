"""Reference ingredient data and a simple blending calculator for suggesting
a starting dairy meal composition.

This is a rule-based calculation (the "Pearson Square" method - standard,
long-established practice in animal nutrition, not something learned from
data) against typical published crude-protein values for common Kenyan feed
ingredients. It is NOT a trained ML model: there is no training data
anywhere in this app for "the ideal feed mix," so calling this AI/ML would
be dishonest. It's a legitimate, useful calculator - always returned as an
editable starting point, never applied silently.
"""

REFERENCE_INGREDIENTS = [
    {'name': 'Maize germ', 'crude_protein_pct': 10},
    {'name': 'Wheat pollard', 'crude_protein_pct': 15},
    {'name': 'Cottonseed cake', 'crude_protein_pct': 40},
    {'name': 'Sunflower cake', 'crude_protein_pct': 35},
    {'name': 'Soybean meal', 'crude_protein_pct': 44},
    {'name': 'Fishmeal', 'crude_protein_pct': 60},
]

MINERAL_PCT = 2
SALT_PCT = 1


def suggest_composition(target_protein_pct, energy_ingredient='Maize germ', protein_ingredient='Cottonseed cake'):
    """Blend one low-protein 'energy' carrier and one high-protein
    concentrate, topped up with a fixed mineral/salt share, to hit an
    overall target crude-protein % (the standard 'Pearson Square' two-
    ingredient blend). Returns (ingredients list of {name, percent} summing
    to 100, achieved crude-protein %)."""
    by_name = {i['name']: i for i in REFERENCE_INGREDIENTS}
    energy = by_name[energy_ingredient]
    protein = by_name[protein_ingredient]

    bulk_pct = 100 - MINERAL_PCT - SALT_PCT
    low, high = energy['crude_protein_pct'], protein['crude_protein_pct']
    if high == low:
        protein_fraction = 0
    else:
        protein_fraction = (target_protein_pct - low) / (high - low)
        protein_fraction = max(0, min(1, protein_fraction))

    protein_pct = round(bulk_pct * protein_fraction, 1)
    energy_pct = round(bulk_pct - protein_pct, 1)

    ingredients = [
        {'name': energy['name'], 'percent': energy_pct},
        {'name': protein['name'], 'percent': protein_pct},
        {'name': 'Mineral premix', 'percent': MINERAL_PCT},
        {'name': 'Salt', 'percent': SALT_PCT},
    ]
    achieved_protein_pct = round((energy_pct * low + protein_pct * high) / 100, 1)
    return ingredients, achieved_protein_pct
