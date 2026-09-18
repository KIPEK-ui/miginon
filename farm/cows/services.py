from decimal import Decimal


def estimate_weight_from_girth(heart_girth_cm):
    """Girth-only liveweight estimate (kg), the same cube-of-girth
    approximation printed on physical cattle weigh tapes - lets a farmer
    without a scale get a usable weight from one tape measurement around
    the chest just behind the front legs. Body-length-adjusted (Schaeffer)
    formulas are more accurate but need a second measurement most
    smallholders don't take."""
    girth = Decimal(heart_girth_cm)
    return round(girth ** 3 / Decimal('11800'), 1)
