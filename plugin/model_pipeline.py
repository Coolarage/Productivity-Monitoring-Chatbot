from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd

from .schemas import ProductivityLabel

# Import the provided preprocessing logic.
# Assumes preprocessing_pipeline.py is available on PYTHONPATH / in project root.
from preprocessing_pipeline import MODEL_FEATURES, engineer_features


class ProductivityModelPipeline:
    """
    Wraps the preprocessing + Random Forest model so the rest of the plugin
    deals only with clean, structured inputs/outputs.
    """

    def __init__(self, model_path: str) -> None:
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Could not find model file at '{model_path}'. "
                "Ensure productivity_model.pkl is deployed with the plugin."
            )
        # Use joblib to load scikit-learn models (compatible with joblib.dump output).
        self._model = joblib.load(model_path)

        # Sanity check: verify that the model can accept the expected features
        if not hasattr(self._model, "predict"):
            raise ValueError(
                "Loaded model does not expose a 'predict' method. "
                "Expected a scikit-learn compatible estimator."
            )

    def predict(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run full pipeline: raw KPI record -> engineered features -> prediction.

        Returns a dict that includes:
        - features: engineered feature dict
        - label: ProductivityLabel
        - proba_decline: optional probability for decline class
        """
        feature_df: pd.DataFrame = engineer_features(raw_record)

        # Convert to model input
        X = feature_df[MODEL_FEATURES]
        preds = self._model.predict(X)

        # Map numeric label to meaningful enum; assume model outputs 0/1
        raw_pred = int(preds[0])
        label = (
            ProductivityLabel.DECLINE_RISK
            if raw_pred == 1
            else ProductivityLabel.NO_DECLINE
        )

        proba_decline = None
        if hasattr(self._model, "predict_proba"):
            proba = self._model.predict_proba(X)
            # Assume index 1 corresponds to decline class
            proba_decline = float(proba[0][1])

        features_dict = {col: float(feature_df.iloc[0][col]) for col in MODEL_FEATURES}

        return {
            "features": features_dict,
            "label": label,
            "proba_decline": proba_decline,
        }


@lru_cache(maxsize=1)
def get_model_pipeline(model_path: str | None = None) -> ProductivityModelPipeline:
    """
    Singleton-style accessor for the pipeline, so the model is loaded once.
    """
    effective_model_path = (
        model_path
        or os.getenv("PRODUCTIVITY_MODEL_PATH")
        or os.path.join(os.getcwd(), "productivity_model.pkl")
    )
    return ProductivityModelPipeline(effective_model_path)

