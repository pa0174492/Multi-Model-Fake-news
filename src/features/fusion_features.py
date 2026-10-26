"""
Multimodal Fusion Feature Dataset Builder.

Aligns text embeddings, vision embeddings, baseline predictions, prompt learning scores,
cross-modal consistency indicators, and metadata features into a structured tabular schema.
"""

import os
import json
import logging
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

logger = logging.getLogger(__name__)


class MultimodalFeatureAligner:
    """
    Constructs aligned multimodal feature matrices and exports comprehensive feature schemas.
    """

    def __init__(self, project_dim: int = 128):
        self.project_dim = project_dim
        self.text_pca = PCA(n_components=project_dim, random_state=42)
        self.vision_pca = PCA(n_components=project_dim, random_state=42)
        self.is_fitted = False
        self.feature_names: List[str] = []

    def fit_cross_modal_projector(self, text_embs: np.ndarray, vision_embs: np.ndarray):
        """Fits dimensionality reduction to project text and vision into common latent space."""
        logger.info(f"Fitting cross-modal alignment projectors to dim={self.project_dim}...")
        self.text_pca.fit(text_embs)
        self.vision_pca.fit(vision_embs)
        self.is_fitted = True

    def compute_cross_modal_features(
        self,
        text_embs: np.ndarray,
        vision_embs: np.ndarray,
        img_masks: np.ndarray
    ) -> np.ndarray:
        """
        Computes projected cross-modal alignment signals:
        - projected_cosine_sim
        - projected_l2_diff
        """
        if not self.is_fitted:
            raise RuntimeError("Cross-modal projector must be fitted before computing features.")

        t_proj = self.text_pca.transform(text_embs)
        t_proj = t_proj / (np.linalg.norm(t_proj, axis=1, keepdims=True) + 1e-9)

        v_proj = self.vision_pca.transform(vision_embs)
        v_proj = v_proj / (np.linalg.norm(v_proj, axis=1, keepdims=True) + 1e-9)

        # Cosine similarity between projected modalities
        cos_sim = np.sum(t_proj * v_proj, axis=1)
        # L2 distance between projected modalities
        l2_diff = np.linalg.norm(t_proj - v_proj, axis=1)

        # Zero out cross-modal similarity when image is missing/invalid
        cos_sim[img_masks == 0] = 0.0
        l2_diff[img_masks == 0] = 2.0  # max divergence default

        return np.column_stack([cos_sim, l2_diff]).astype(np.float32)

    @staticmethod
    def extract_text_metadata_features(df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Extracts engineered text surface and Reddit metadata features."""
        feats = []
        feature_names = [
            "title_char_length",
            "title_word_count",
            "uppercase_ratio",
            "exclamation_count",
            "question_count",
            "log_score",
            "log_num_comments",
            "upvote_ratio"
        ]

        for _, row in df.iterrows():
            title = str(row.get("clean_title", ""))
            c_len = len(title)
            w_count = len(title.split())
            caps = sum(1 for c in title if c.isupper())
            caps_ratio = (caps / max(c_len, 1))
            excl = title.count("!")
            ques = title.count("?")

            score_raw = row.get("score", 0)
            score = float(score_raw) if pd.notna(score_raw) else 0.0
            log_score = np.log1p(max(score, 0.0))

            comments_raw = row.get("num_comments", 0)
            comments = float(comments_raw) if pd.notna(comments_raw) else 0.0
            log_comments = np.log1p(max(comments, 0.0))

            upvote_raw = row.get("upvote_ratio", 0.5)
            upvote = float(upvote_raw) if pd.notna(upvote_raw) else 0.5

            feats.append([
                c_len,
                w_count,
                caps_ratio,
                excl,
                ques,
                log_score,
                log_comments,
                upvote
            ])

        meta_arr = np.nan_to_num(np.array(feats, dtype=np.float32), nan=0.0)
        return meta_arr, feature_names

    def build_fusion_matrix(
        self,
        df: pd.DataFrame,
        text_embs: np.ndarray,
        vision_embs: np.ndarray,
        img_masks: np.ndarray,
        prompt_feats: np.ndarray,
        text_probs: np.ndarray,
        img_probs: np.ndarray,
        is_train: bool = False
    ) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
        """
        Assembles complete multimodal feature matrix and schema.
        """
        if is_train:
            self.fit_cross_modal_projector(text_embs, vision_embs)

        cross_modal_feats = self.compute_cross_modal_features(text_embs, vision_embs, img_masks)
        meta_feats, meta_names = self.extract_text_metadata_features(df)

        # Baseline probability divergence
        prob_divergence = np.abs(text_probs - img_probs)

        # Compile feature columns
        feature_blocks = [
            text_embs,                                     # (N, 384)
            vision_embs,                                   # (N, 512)
            img_masks.reshape(-1, 1).astype(np.float32),   # (N, 1)
            prompt_feats,                                  # (N, 3)
            text_probs.reshape(-1, 1).astype(np.float32),  # (N, 1)
            img_probs.reshape(-1, 1).astype(np.float32),   # (N, 1)
            prob_divergence.reshape(-1, 1).astype(np.float32), # (N, 1)
            cross_modal_feats,                             # (N, 2)
            meta_feats                                     # (N, 8)
        ]

        X_fusion = np.hstack(feature_blocks).astype(np.float32)
        X_fusion = np.nan_to_num(X_fusion, nan=0.0, posinf=0.0, neginf=0.0)

        # Feature Names
        names = []
        names.extend([f"text_emb_{i}" for i in range(text_embs.shape[1])])
        names.extend([f"img_emb_{i}" for i in range(vision_embs.shape[1])])
        names.append("has_valid_image")
        names.extend(["prompt_cos_real", "prompt_cos_fake", "prompt_prob_fake"])
        names.append("text_baseline_prob_fake")
        names.append("image_baseline_prob_fake")
        names.append("modality_prob_divergence")
        names.extend(["cross_modal_cosine_sim", "cross_modal_l2_diff"])
        names.extend(meta_names)

        self.feature_names = names

        schema = {
            "total_features": len(names),
            "feature_groups": {
                "text_embeddings": {
                    "count": text_embs.shape[1],
                    "range": [0, text_embs.shape[1] - 1],
                    "extractor": "sentence-transformers/all-MiniLM-L6-v2"
                },
                "vision_embeddings": {
                    "count": vision_embs.shape[1],
                    "range": [text_embs.shape[1], text_embs.shape[1] + vision_embs.shape[1] - 1],
                    "extractor": "resnet18_imagenet"
                },
                "prompt_learning": {
                    "count": 3,
                    "features": ["prompt_cos_real", "prompt_cos_fake", "prompt_prob_fake"]
                },
                "modality_baselines": {
                    "count": 3,
                    "features": ["text_baseline_prob_fake", "image_baseline_prob_fake", "modality_prob_divergence"]
                },
                "cross_modal_alignment": {
                    "count": 2,
                    "features": ["cross_modal_cosine_sim", "cross_modal_l2_diff"]
                },
                "metadata_surface": {
                    "count": len(meta_names),
                    "features": meta_names
                }
            },
            "feature_names": names
        }

        return X_fusion, names, schema
