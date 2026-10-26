"""
XGBoost Multimodal Fusion Model.

Trains extreme gradient boosted decision trees over aligned multimodal representations
with early stopping and feature importance analysis.
"""

import os
import json
import logging
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import xgboost as xgb
import joblib

logger = logging.getLogger(__name__)


class XGBoostFusionModel:
    """XGBoost Multimodal Fusion Classifier."""

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 6,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        random_state: int = 42
    ):
        self.params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "random_state": random_state,
            "eval_metric": "logloss",
            "n_jobs": -1
        }
        self.model: Optional[xgb.XGBClassifier] = None
        self.feature_names: List[str] = []
        self.is_fitted = False

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        feature_names: List[str],
        early_stopping_rounds: int = 25
    ):
        """
        Trains XGBoost fusion model with early stopping on validation split.
        """
        logger.info(f"Training XGBoost Fusion Model on {X_train.shape[0]} samples with {X_train.shape[1]} features...")
        self.feature_names = feature_names

        self.model = xgb.XGBClassifier(
            **self.params,
            early_stopping_rounds=early_stopping_rounds
        )

        self.model.fit(
            X_train,
            y_train,
            eval_set=[(X_train, y_train), (X_val, y_val)],
            verbose=False
        )
        self.is_fitted = True
        logger.info(f"XGBoost training complete. Best iteration: {self.model.best_iteration}")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predicts probability of is_fake=1."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Fusion model is not fitted.")
        return self.model.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Predicts binary classification labels (0=Real, 1=Fake)."""
        return (self.predict_proba(X) >= threshold).astype(int)

    def get_feature_importances(self, top_k: int = 25) -> Dict[str, float]:
        """Returns top feature importances by Gain."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Fusion model is not fitted.")
        raw_importances = self.model.feature_importances_
        named_imp = {name: float(val) for name, val in zip(self.feature_names, raw_importances)}
        sorted_imp = dict(sorted(named_imp.items(), key=lambda item: item[1], reverse=True)[:top_k])
        return sorted_imp

    def save(self, model_dir: str):
        """Saves model in both native XGBoost JSON and joblib formats."""
        os.makedirs(model_dir, exist_ok=True)
        json_path = os.path.join(model_dir, "fusion_model.json")
        joblib_path = os.path.join(model_dir, "fusion_model.joblib")
        params_path = os.path.join(model_dir, "model_params.json")

        self.model.save_model(json_path)
        joblib.dump(self.model, joblib_path)

        with open(params_path, "w") as f:
            json.dump({
                "params": self.params,
                "best_iteration": int(self.model.best_iteration) if hasattr(self.model, "best_iteration") else None,
                "feature_count": len(self.feature_names)
            }, f, indent=2)

        logger.info(f"Fusion model saved to {json_path} and {joblib_path}")

    def load(self, model_dir: str, feature_names: List[str]):
        """Loads model from disk."""
        joblib_path = os.path.join(model_dir, "fusion_model.joblib")
        if os.path.exists(joblib_path):
            self.model = joblib.load(joblib_path)
        else:
            json_path = os.path.join(model_dir, "fusion_model.json")
            self.model = xgb.XGBClassifier()
            self.model.load_model(json_path)

        self.feature_names = feature_names
        self.is_fitted = True
        logger.info(f"Fusion model successfully loaded from {model_dir}")
