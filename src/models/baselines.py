"""
Unimodal Baselines for Text-Only and Image-Only Fake News Detection.

Implements Ridge / Logistic Regression / MLP unimodal classifiers.
Computes leak-free out-of-fold probability estimates for fusion training via 5-fold CV,
and full-fitted predictions for validation and test evaluation.
"""

import logging
from typing import Dict, Tuple, Any
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score
import joblib

logger = logging.getLogger(__name__)


class ModalityBaseline:
    """Base class for unimodal baseline models."""

    def __init__(self, name: str, C: float = 1.0, max_iter: int = 1000):
        self.name = name
        self.clf = LogisticRegression(C=C, max_iter=max_iter, random_state=42, solver="lbfgs")
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        """Fits baseline model on the entire feature matrix."""
        logger.info(f"Fitting {self.name} on {X.shape[0]} samples...")
        self.clf.fit(X, y)
        self.is_fitted = True

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Returns probability of positive class (is_fake=1)."""
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} is not fitted yet.")
        return self.clf.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Returns binary predictions."""
        return (self.predict_proba(X) >= threshold).astype(int)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """Evaluates baseline model metrics."""
        probs = self.predict_proba(X)
        preds = (probs >= 0.5).astype(int)

        acc = accuracy_score(y, preds)
        prec, rec, f1, _ = precision_recall_fscore_support(y, preds, average="binary", zero_division=0)
        auc = roc_auc_score(y, probs)

        metrics = {
            f"{self.name}_accuracy": float(acc),
            f"{self.name}_precision": float(prec),
            f"{self.name}_recall": float(rec),
            f"{self.name}_f1": float(f1),
            f"{self.name}_roc_auc": float(auc)
        }
        logger.info(f"{self.name} Evaluation: Acc={acc:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
        return metrics

    def compute_oof_predictions(self, X: np.ndarray, y: np.ndarray, n_splits: int = 5) -> np.ndarray:
        """
        Computes leak-free Out-Of-Fold predictions via Stratified K-Fold.
        Ensures training fusion features have realistic, non-overfitted baseline signals.
        """
        logger.info(f"Computing {n_splits}-fold OOF predictions for {self.name}...")
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        oof_probs = np.zeros(len(y), dtype=np.float32)

        for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
            fold_clf = LogisticRegression(C=1.0, max_iter=1000, random_state=42 + fold)
            fold_clf.fit(X[train_idx], y[train_idx])
            oof_probs[val_idx] = fold_clf.predict_proba(X[val_idx])[:, 1]

        return oof_probs

    def save(self, file_path: str):
        joblib.dump(self.clf, file_path)

    def load(self, file_path: str):
        self.clf = joblib.load(file_path)
        self.is_fitted = True


class TextOnlyBaseline(ModalityBaseline):
    def __init__(self, C: float = 1.0):
        super().__init__(name="text_only_baseline", C=C)


class ImageOnlyBaseline(ModalityBaseline):
    def __init__(self, C: float = 1.0):
        super().__init__(name="image_only_baseline", C=C)
