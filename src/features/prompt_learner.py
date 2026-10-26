"""
Prompt-Based Text Classification Experiment and Feature Generator.

Implements prompt learning for fake news detection using verbalizer anchor mapping,
prompt template construction, and veracity likelihood scoring.
"""

import json
import logging
from typing import List, Dict, Tuple, Any
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score
from scipy.special import expit

from src.features.text_encoder import TextEncoder

logger = logging.getLogger(__name__)

# Prompt Learning Experiment Template and Verbalizer Specification
PROMPT_EXPERIMENT_CONFIG = {
    "experiment_name": "Prompt-Based Headline Veracity Scoring",
    "prompt_template": "News headline: \"{headline}\". Fact-check assessment and veracity report:",
    "verbalizer_spec": {
        "real_anchors": [
            "This news reporting is completely genuine, authentic, and verified as real.",
            "Verified factual news event reported accurately from reliable sources.",
            "Legitimate journalistic reporting with verifiable real facts."
        ],
        "fake_anchors": [
            "This news reporting is fabricated, misleading, deceptive, and completely fake.",
            "False claim, satirical manipulation, fabricated hoax, and disinformation.",
            "Unverified fake news headline designed to mislead the public."
        ]
    },
    "scoring_formulation": "Differential cosine similarity between prompt-augmented headline and verbalizer anchors"
}


class PromptLearner:
    """
    Executes prompt learning formulation, computes verbalizer scores,
    calibrates classification thresholds, and produces prompt features for fusion.
    """

    def __init__(self, text_encoder: TextEncoder):
        self.text_encoder = text_encoder
        self.config = PROMPT_EXPERIMENT_CONFIG
        self.template = self.config["prompt_template"]

        logger.info("Initializing PromptLearner verbalizer anchor embeddings...")
        # Precompute mean embedding for real verbalizers
        real_embs = self.text_encoder.encode_batch(self.config["verbalizer_spec"]["real_anchors"])
        self.real_anchor_vector = np.mean(real_embs, axis=0)
        self.real_anchor_vector /= (np.linalg.norm(self.real_anchor_vector) + 1e-9)

        # Precompute mean embedding for fake verbalizers
        fake_embs = self.text_encoder.encode_batch(self.config["verbalizer_spec"]["fake_anchors"])
        self.fake_anchor_vector = np.mean(fake_embs, axis=0)
        self.fake_anchor_vector /= (np.linalg.norm(self.fake_anchor_vector) + 1e-9)

        self.calibrated_threshold = 0.0
        self.scaling_factor = 10.0

    def format_prompt(self, headline: str) -> str:
        """Formats the input headline into the prompt template."""
        clean_hl = str(headline).strip().strip('"')
        return self.template.format(headline=clean_hl)

    def compute_prompt_scores(self, headlines: List[str]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Computes for each headline:
        1) affinity to real verbalizers: cos_real
        2) affinity to fake verbalizers: cos_fake
        3) prompt fake probability: prob_fake = sigmoid(scale * (cos_fake - cos_real))
        """
        prompts = [self.format_prompt(h) for h in headlines]
        prompt_embeddings = self.text_encoder.encode_batch(prompts)  # (N, D), already L2 normalized

        cos_real = np.dot(prompt_embeddings, self.real_anchor_vector)  # (N,)
        cos_fake = np.dot(prompt_embeddings, self.fake_anchor_vector)  # (N,)

        diff = cos_fake - cos_real
        prob_fake = expit(self.scaling_factor * diff)

        return cos_real, cos_fake, prob_fake

    def calibrate(self, val_headlines: List[str], val_labels: np.ndarray) -> Dict[str, Any]:
        """
        Calibrates optimal classification threshold on validation set and logs experiment metrics.
        """
        cos_real, cos_fake, prob_fake = self.compute_prompt_scores(val_headlines)

        # Grid search over threshold
        thresholds = np.linspace(0.1, 0.9, 81)
        best_f1 = -1.0
        best_thresh = 0.5

        for th in thresholds:
            preds = (prob_fake >= th).astype(int)
            _, _, f1, _ = precision_recall_fscore_support(val_labels, preds, average="binary", zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = th

        self.calibrated_threshold = best_thresh
        val_preds = (prob_fake >= best_thresh).astype(int)

        acc = accuracy_score(val_labels, val_preds)
        prec, rec, f1, _ = precision_recall_fscore_support(val_labels, val_preds, average="binary", zero_division=0)
        roc_auc = roc_auc_score(val_labels, prob_fake)

        metrics = {
            "calibrated_threshold": float(best_thresh),
            "val_accuracy": float(acc),
            "val_precision": float(prec),
            "val_recall": float(rec),
            "val_f1": float(f1),
            "val_roc_auc": float(roc_auc),
            "template": self.template,
            "verbalizer_spec": self.config["verbalizer_spec"]
        }
        logger.info(f"Prompt learning calibrated: Thresh={best_thresh:.3f}, Acc={acc:.4f}, F1={f1:.4f}, AUC={roc_auc:.4f}")
        return metrics

    def extract_prompt_features(self, headlines: List[str]) -> np.ndarray:
        """
        Extracts 3 prompt learning features per sample:
        [prompt_cos_real, prompt_cos_fake, prompt_fake_probability]
        """
        cos_real, cos_fake, prob_fake = self.compute_prompt_scores(headlines)
        return np.column_stack([cos_real, cos_fake, prob_fake]).astype(np.float32)
