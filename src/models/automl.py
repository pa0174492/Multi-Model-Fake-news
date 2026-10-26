"""
AutoML Candidate Comparison Module.

Compares multiple model candidate families during the offline training phase,
benchmarks their validation metrics and runtime, and selects the winning architecture
for frozen, low-latency inference.
"""

import time
import json
import logging
from typing import Dict, List, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.neural_network import MLPClassifier
import xgboost as xgb
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score

logger = logging.getLogger(__name__)


class AutoMLComparator:
    """
    Evaluates multiple candidate model architectures on multimodal fusion representations
    and selects the optimal architecture based on validation performance.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.leaderboard: List[Dict[str, Any]] = []
        self.best_candidate_name: str = ""
        self.best_candidate_model: Any = None

    def get_candidate_pool(self) -> Dict[str, Any]:
        """Defines candidate models spanning linear, bagging, neural, and gradient boosting families."""
        return {
            "LogisticRegression": LogisticRegression(
                C=1.0, max_iter=1000, random_state=self.random_state, solver="lbfgs"
            ),
            "RandomForest": RandomForestClassifier(
                n_estimators=100, max_depth=12, n_jobs=-1, random_state=self.random_state
            ),
            "ExtraTrees": ExtraTreesClassifier(
                n_estimators=100, max_depth=12, n_jobs=-1, random_state=self.random_state
            ),
            "MLPClassifier": MLPClassifier(
                hidden_layer_sizes=(128, 64), max_iter=250, random_state=self.random_state, early_stopping=True
            ),
            "XGBoost": xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.random_state,
                eval_metric="logloss",
                n_jobs=-1
            )
        }

    def run_comparison(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> pd.DataFrame:
        """
        Trains and benchmarks all candidates on validation set.
        """
        logger.info(f"Running AutoML candidate comparison across {len(self.get_candidate_pool())} model architectures...")
        candidates = self.get_candidate_pool()
        records = []

        best_score = -1.0

        for name, model in candidates.items():
            logger.info(f"--> Training candidate: {name}...")
            start_time = time.time()

            try:
                model.fit(X_train, y_train)
                train_time = time.time() - start_time

                # Validation predictions
                probs = model.predict_proba(X_val)[:, 1]
                preds = (probs >= 0.5).astype(int)

                acc = accuracy_score(y_val, preds)
                prec, rec, f1, _ = precision_recall_fscore_support(y_val, preds, average="binary", zero_division=0)
                macro_f1, _, _, _ = precision_recall_fscore_support(y_val, preds, average="macro", zero_division=0)
                roc_auc = roc_auc_score(y_val, probs)

                record = {
                    "candidate": name,
                    "val_accuracy": round(float(acc), 4),
                    "val_macro_f1": round(float(macro_f1), 4),
                    "val_binary_f1": round(float(f1), 4),
                    "val_precision": round(float(prec), 4),
                    "val_recall": round(float(rec), 4),
                    "val_roc_auc": round(float(roc_auc), 4),
                    "train_time_sec": round(float(train_time), 2),
                    "status": "SUCCESS"
                }

                # We select based on ROC-AUC + Macro F1
                selection_metric = macro_f1
                if selection_metric > best_score:
                    best_score = selection_metric
                    self.best_candidate_name = name
                    self.best_candidate_model = model

            except Exception as e:
                logger.error(f"Candidate {name} failed: {e}")
                record = {
                    "candidate": name,
                    "val_accuracy": 0.0,
                    "val_macro_f1": 0.0,
                    "val_binary_f1": 0.0,
                    "val_precision": 0.0,
                    "val_recall": 0.0,
                    "val_roc_auc": 0.0,
                    "train_time_sec": 0.0,
                    "status": f"FAILED_{e}"
                }

            records.append(record)
            logger.info(f"    [{name}] Acc={record['val_accuracy']}, F1={record['val_macro_f1']}, AUC={record['val_roc_auc']}, Time={record['train_time_sec']}s")

        df_leaderboard = pd.DataFrame(records).sort_values(by="val_macro_f1", ascending=False).reset_index(drop=True)
        self.leaderboard = df_leaderboard.to_dict(orient="records")
        logger.info(f"AutoML winning candidate: {self.best_candidate_name} (Macro F1 = {best_score:.4f})")
        return df_leaderboard

    def save_leaderboard(self, out_path: str):
        with open(out_path, "w") as f:
            json.dump({
                "selection_criterion": "val_macro_f1",
                "winning_candidate": self.best_candidate_name,
                "leaderboard": self.leaderboard
            }, f, indent=2)
