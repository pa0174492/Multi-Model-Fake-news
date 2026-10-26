"""
SHAP Explanations for the Trained Multimodal Fusion Model.

Computes global TreeExplainer importances and local feature contributions
for individual test samples to explain multimodal fake news detection decisions.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
import numpy as np
import shap
import xgboost as xgb

logger = logging.getLogger(__name__)


class MultimodalSHAPExplainer:
    """
    Computes SHAP explanations on the trained XGBoost fusion model.
    """

    def __init__(self, model: xgb.XGBClassifier, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names
        logger.info("Initializing shap.TreeExplainer on trained XGBoost fusion model...")
        self.explainer = shap.TreeExplainer(model)
        exp_val = self.explainer.expected_value
        if isinstance(exp_val, (list, np.ndarray)):
            exp_val = exp_val[1] if len(exp_val) > 1 else (exp_val[0] if len(exp_val) > 0 else 0.0)
        self.expected_value = float(exp_val)

    def compute_global_explanations(self, X_sample: np.ndarray, top_k: int = 25) -> Dict[str, Any]:
        """
        Computes mean absolute SHAP values across evaluation samples to rank global feature importance.
        """
        logger.info(f"Computing global SHAP values across {X_sample.shape[0]} background samples...")
        shap_values = self.explainer.shap_values(X_sample)

        # In binary XGBoost, shap_values can be (N, D) or list of classes
        if isinstance(shap_values, list):
            shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]

        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
        ranked_indices = np.argsort(mean_abs_shap)[::-1]

        global_ranking = []
        for rank, idx in enumerate(ranked_indices[:top_k], 1):
            global_ranking.append({
                "rank": rank,
                "feature": self.feature_names[idx],
                "mean_abs_shap": round(float(mean_abs_shap[idx]), 5)
            })

        return {
            "expected_value": self.expected_value,
            "sample_count": X_sample.shape[0],
            "top_global_features": global_ranking
        }

    def explain_sample(
        self,
        x_vector: np.ndarray,
        sample_metadata: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Generates local explanation for a single prediction vector.
        Shows top features pushing toward Fake (+SHAP) vs Real (-SHAP).
        """
        x_2d = x_vector.reshape(1, -1)
        shap_vals = self.explainer.shap_values(x_2d)
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[1]

        vals = shap_vals[0]
        prob = float(self.model.predict_proba(x_2d)[0, 1])
        prediction = "Fake" if prob >= 0.5 else "Real"

        # Separate positive and negative contributors
        features_with_impact = []
        for name, val, f_val in zip(self.feature_names, vals, x_vector):
            features_with_impact.append({
                "feature": name,
                "feature_value": round(float(f_val), 4),
                "shap_value": round(float(val), 5),
                "direction": "Pushes toward Fake" if val > 0 else "Pushes toward Real"
            })

        # Top positive contributors (pushing toward Fake)
        positive_contributors = sorted(
            [f for f in features_with_impact if f["shap_value"] > 0],
            key=lambda x: x["shap_value"],
            reverse=True
        )[:top_k]

        # Top negative contributors (pushing toward Real)
        negative_contributors = sorted(
            [f for f in features_with_impact if f["shap_value"] < 0],
            key=lambda x: x["shap_value"]
        )[:top_k]

        explanation = {
            "prediction": prediction,
            "fake_probability": round(prob, 4),
            "base_value": round(self.expected_value, 4),
            "top_positive_contributors_fake": positive_contributors,
            "top_negative_contributors_real": negative_contributors,
            "sample_metadata": sample_metadata or {}
        }
        return explanation

    def save_summary(self, X_eval: np.ndarray, out_path: str):
        """Generates and saves global SHAP summary to JSON."""
        summary = self.compute_global_explanations(X_eval)
        with open(out_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"SHAP summary saved to {out_path}")
