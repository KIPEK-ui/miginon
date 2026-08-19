"""Fits a Ridge regression on a farm's own historical cow-day rows,
entirely on-demand at request time (see the project plan's dependency
spike: this app runs on Vercel serverless, no scheduled/background
training). A single farm's data is small enough (dozens to low-thousands
of rows) that this fits comfortably in the request budget. Features are
standardized first so the fitted coefficients are directly comparable and
usable for exact per-feature explanation (see explain.py)."""

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_NAMES, build_training_rows

MIN_ROWS = 30


class TrainedModel:
    def __init__(self, model, scaler, feature_names, mean_liters, row_count):
        self.model = model
        self.scaler = scaler
        self.feature_names = feature_names
        self.mean_liters = mean_liters
        self.row_count = row_count

    def predict_one(self, raw_features):
        x = np.array([[raw_features[name] for name in self.feature_names]])
        x_scaled = self.scaler.transform(x)
        predicted = float(self.model.predict(x_scaled)[0])
        return predicted, x_scaled[0]


def train_farm_model(farm, cow=None):
    """Returns a TrainedModel, or None if there isn't enough history yet -
    the cold-start guard mentioned in the plan."""
    rows = build_training_rows(farm, cow=cow)
    if len(rows) < MIN_ROWS:
        return None

    x = np.array([[r['raw'][name] for name in FEATURE_NAMES] for r in rows])
    y = np.array([r['liters'] for r in rows])

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)

    model = Ridge(alpha=1.0)
    model.fit(x_scaled, y)

    return TrainedModel(model, scaler, FEATURE_NAMES, float(y.mean()), len(rows))
