"""
Evaluation Metrics and Comparative Benchmarking Module.

Computes comprehensive classification metrics (Accuracy, Macro/Binary F1, Precision,
Recall, ROC-AUC, Average Precision, Confusion Matrix) and multi-model benchmark comparisons.
"""

import json
import logging
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    classification_report,
    brier_score_loss
)

logger = logging.getLogger(__name__)


def compute_comprehensive_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
    model_name: str = "Model"
) -> Dict[str, Any]:
    """
    Computes full set of binary classification metrics.
    """
    y_pred = (y_prob >= threshold).astype(int)

    acc = accuracy_score(y_true, y_pred)
    prec_bin = precision_score(y_true, y_pred, zero_division=0)
    rec_bin = recall_score(y_true, y_pred, zero_division=0)
    f1_bin = f1_score(y_true, y_pred, zero_division=0)

    prec_macro = precision_score(y_true, y_pred, average="macro", zero_division=0)
    rec_macro = recall_score(y_true, y_pred, average="macro", zero_division=0)
    f1_macro = f1_score(y_true, y_pred, average="macro", zero_division=0)

    try:
        roc_auc = roc_auc_score(y_true, y_prob)
    except Exception:
        roc_auc = 0.0

    try:
        pr_auc = average_precision_score(y_true, y_prob)
    except Exception:
        pr_auc = 0.0

    brier = brier_score_loss(y_true, y_prob)
    cm = confusion_matrix(y_true, y_pred).tolist()
    report = classification_report(y_true, y_pred, target_names=["Real", "Fake"], output_dict=True, zero_division=0)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    return {
        "model_name": model_name,
        "sample_count": int(len(y_true)),
        "accuracy": round(float(acc), 4),
        "macro_f1": round(float(f1_macro), 4),
        "macro_precision": round(float(prec_macro), 4),
        "macro_recall": round(float(rec_macro), 4),
        "binary_f1": round(float(f1_bin), 4),
        "binary_precision": round(float(prec_bin), 4),
        "binary_recall": round(float(rec_bin), 4),
        "roc_auc": round(float(roc_auc), 4),
        "average_precision_pr_auc": round(float(pr_auc), 4),
        "brier_score": round(float(brier), 4),
        "confusion_matrix": {
            "true_negatives_real": int(tn),
            "false_positives_fake": int(fp),
            "false_negatives_real": int(fn),
            "true_positives_fake": int(tp)
        },
        "classification_report": report
    }


def build_benchmark_summary(
    eval_dict: Dict[str, Dict[str, Any]]
) -> pd.DataFrame:
    """
    Creates comparative benchmark table across text-only, image-only, prompt learning, and fusion models.
    """
    rows = []
    for model_name, metrics in eval_dict.items():
        rows.append({
            "Model Architecture": model_name,
            "Accuracy": metrics["accuracy"],
            "Macro F1": metrics["macro_f1"],
            "Binary F1": metrics["binary_f1"],
            "Precision": metrics["binary_precision"],
            "Recall": metrics["binary_recall"],
            "ROC-AUC": metrics["roc_auc"],
            "PR-AUC": metrics["average_precision_pr_auc"]
        })
    df = pd.DataFrame(rows).sort_values(by="Macro F1", ascending=False).reset_index(drop=True)
    return df
