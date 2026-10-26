"""
Versioned Multimodal Fake News Detection Inference Pipeline.

Provides low-latency, end-to-end inference and SHAP explainability interfaces
for arbitrary text-image inputs.
"""

import os
import json
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Tuple
import numpy as np
import pandas as pd
import joblib

logger = logging.getLogger(__name__)


class MultimodalInferencePipeline:
    """
    Production-grade versioned inference pipeline for multimodal fake news detection.
    """

    def __init__(self, artifact_root: str = "artifacts", version: str = "v1.0.0"):
        self.artifact_root = artifact_root
        self.version = version
        self.version_dir = os.path.join(artifact_root, version)
        self.is_loaded = False
        self._load_lock = threading.Lock()

        # Components to be loaded
        self.text_encoder = None
        self.vision_encoder = None
        self.prompt_learner = None
        self.feature_aligner = None
        self.text_baseline = None
        self.image_baseline = None
        self.fusion_model = None
        self.shap_explainer = None
        self.feature_schema: Dict[str, Any] = {}
        self.preprocessing_config: Dict[str, Any] = {}
        self.label_mapping: Dict[str, Any] = {}

    def load(self):
        """Loads all versioned artifacts from disk (thread-safe)."""
        with self._load_lock:
            if self.is_loaded:
                return
            logger.info(f"Loading MultimodalInferencePipeline version '{self.version}' from {self.version_dir}...")
            if not os.path.exists(self.version_dir):
                raise FileNotFoundError(f"Version directory not found: {self.version_dir}")

            # Lazy import heavy models only when pipeline loads
            from src.features.text_encoder import TextEncoder
            from src.features.vision_encoder import VisionEncoder
            from src.features.prompt_learner import PromptLearner
            from src.features.fusion_features import MultimodalFeatureAligner
            from src.explainability.shap_explainer import MultimodalSHAPExplainer

            # Load configurations and schemas
            with open(os.path.join(self.version_dir, "feature_schema.json"), "r") as f:
                self.feature_schema = json.load(f)
            with open(os.path.join(self.version_dir, "preprocessing_config.json"), "r") as f:
                self.preprocessing_config = json.load(f)
            with open(os.path.join(self.version_dir, "label_mapping.json"), "r") as f:
                self.label_mapping = json.load(f)

            # Initialize feature extractors
            self.text_encoder = TextEncoder()
            self.vision_encoder = VisionEncoder()
            self.prompt_learner = PromptLearner(self.text_encoder)

            # Load models
            self.text_baseline = joblib.load(os.path.join(self.version_dir, "text_baseline.joblib"))
            self.image_baseline = joblib.load(os.path.join(self.version_dir, "image_baseline.joblib"))
            self.fusion_model = joblib.load(os.path.join(self.version_dir, "fusion_model.joblib"))

            # Load alignment projectors
            self.feature_aligner = MultimodalFeatureAligner(project_dim=128)
            self.feature_aligner.text_pca = joblib.load(os.path.join(self.version_dir, "text_pca.joblib"))
            self.feature_aligner.vision_pca = joblib.load(os.path.join(self.version_dir, "vision_pca.joblib"))
            self.feature_aligner.is_fitted = True

            # Initialize SHAP explainer
            feature_names = self.feature_schema["feature_names"]
            self.shap_explainer = MultimodalSHAPExplainer(self.fusion_model, feature_names)

            self.is_loaded = True
            logger.info(f"Inference pipeline '{self.version}' initialized successfully with {len(feature_names)} features.")

    def ensure_loaded(self):
        """Ensures the pipeline is fully initialized before inference."""
        if not self.is_loaded:
            self.load()

    def build_feature_vector(
        self,
        text: str,
        image_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Builds aligned 1D multimodal feature vector for a single input query.
        """
        self.ensure_loaded()

        # 1. Text embedding
        text_emb = self.text_encoder.encode_batch([text])  # (1, 384)

        # 2. Vision embedding & validity
        has_image = 0
        if image_path and os.path.exists(image_path):
            vision_emb, valid_mask = self.vision_encoder.encode_batch([image_path])
            has_image = int(valid_mask[0])
        else:
            vision_emb = np.zeros((1, 512), dtype=np.float32)
            has_image = 0

        # 3. Prompt features
        prompt_feats = self.prompt_learner.extract_prompt_features([text])  # (1, 3)

        # 4. Baseline probabilities
        text_prob = float(self.text_baseline.predict_proba(text_emb)[0])
        if has_image:
            image_prob = float(self.image_baseline.predict_proba(vision_emb)[0])
        else:
            image_prob = 0.5  # neutral uncertainty when image is missing

        # 5. Metadata
        meta_dict = metadata or {}
        df_meta = pd.DataFrame([{
            "clean_title": text,
            "score": meta_dict.get("score", 0),
            "num_comments": meta_dict.get("num_comments", 0),
            "upvote_ratio": meta_dict.get("upvote_ratio", 0.5)
        }])

        # 6. Assemble complete vector matching feature schema
        X_vec, _, _ = self.feature_aligner.build_fusion_matrix(
            df=df_meta,
            text_embs=text_emb,
            vision_embs=vision_emb,
            img_masks=np.array([has_image]),
            prompt_feats=prompt_feats,
            text_probs=np.array([text_prob]),
            img_probs=np.array([image_prob]),
            is_train=False
        )

        modality_scores = {
            "text_baseline_fake_prob": round(text_prob, 4),
            "image_baseline_fake_prob": round(image_prob, 4),
            "prompt_fake_prob": round(float(prompt_feats[0, 2]), 4),
            "has_valid_image": bool(has_image),
            "text_baseline_prob_fake": round(text_prob, 4),
            "image_baseline_prob_fake": round(image_prob, 4),
            "prompt_verbalizer_fake_prob": round(float(prompt_feats[0, 2]), 4),
            "prompt_veracity_score": round(float(prompt_feats[0, 2]), 4),
            "has_image": bool(has_image)
        }

        return X_vec[0], modality_scores

    def predict(
        self,
        text: str,
        image_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """Runs multimodal fake news prediction on a text-image input."""
        x_vec, scores = self.build_feature_vector(text, image_path, metadata)
        fake_prob = float(self.fusion_model.predict_proba(x_vec.reshape(1, -1))[0, 1])
        is_fake = int(fake_prob >= threshold)

        return {
            "prediction": "Fake" if is_fake == 1 else "Real",
            "is_fake_binary": is_fake,
            "fake_probability": round(fake_prob, 4),
            "real_probability": round(1.0 - fake_prob, 4),
            "confidence": round(abs(fake_prob - 0.5) * 2.0, 4),
            "modality_scores": scores,
            "pipeline_version": self.version
        }

    def explain(
        self,
        text: str,
        image_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Runs prediction and generates detailed SHAP local explanation."""
        x_vec, scores = self.build_feature_vector(text, image_path, metadata)
        explanation = self.shap_explainer.explain_sample(
            x_vector=x_vec,
            sample_metadata={"headline": text, "image_path": image_path, "modality_scores": scores},
            top_k=top_k
        )
        explanation["pipeline_version"] = self.version
        return explanation
