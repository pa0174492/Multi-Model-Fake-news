"""
End-to-End Training, AutoML Comparison, Multimodal Fusion, and Artifact Generation Pipeline.

Phase 3 Core Execution:
1. Load verified multimodal splits (Train, Val, Test).
2. Extract pretrained text features (MiniLM-L6-v2, 384-d).
3. Extract pretrained vision features (ResNet-18, 512-d).
4. Run prompt-based text classification experiment and extract verbalizer features.
5. Train text-only and image-only baselines with out-of-fold probability estimation.
6. Build aligned multimodal fusion dataset and feature schema.
7. Perform offline AutoML candidate comparison across 5 diverse model families.
8. Train and tune XGBoost Multimodal Fusion Model with early stopping.
9. Evaluate all models on held-out test split.
10. Generate global and local SHAP explanations using TreeExplainer.
11. Package and persist versioned artifacts, schemas, and configurations.
"""

import os
import sys

# Ensure root repository is in python path
sys.path.insert(0, os.path.abspath("."))

import json
import time
import logging
import joblib
import numpy as np
import pandas as pd

from src.features.text_encoder import TextEncoder
from src.features.vision_encoder import VisionEncoder
from src.features.prompt_learner import PromptLearner
from src.features.fusion_features import MultimodalFeatureAligner
from src.models.baselines import TextOnlyBaseline, ImageOnlyBaseline
from src.models.automl import AutoMLComparator
from src.models.fusion_model import XGBoostFusionModel
from src.explainability.shap_explainer import MultimodalSHAPExplainer
from src.evaluation.metrics import compute_comprehensive_metrics, build_benchmark_summary
from src.artifacts.artifact_manager import ArtifactManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    version = "v1.0.0"
    logger.info(f"========== STARTING PHASE 3 TRAINING PIPELINE (VERSION: {version}) ==========")

    # Directories
    processed_dir = "data/processed"
    cache_dir = os.path.join(processed_dir, "features_cache")
    os.makedirs(cache_dir, exist_ok=True)

    artifact_manager = ArtifactManager(root_dir="artifacts")
    version_dir = artifact_manager.get_version_dir(version)
    os.makedirs(version_dir, exist_ok=True)

    # 1. Load Processed Datasets
    logger.info("--- [Step 1/10] Loading Processed Multimodal Datasets ---")
    train_df = pd.read_csv(os.path.join(processed_dir, "train_multimodal.csv"))
    val_df = pd.read_csv(os.path.join(processed_dir, "val_multimodal.csv"))
    test_df = pd.read_csv(os.path.join(processed_dir, "test_multimodal.csv"))

    logger.info(f"Train samples: {len(train_df)} | Val samples: {len(val_df)} | Test samples: {len(test_df)}")

    y_train = train_df["is_fake"].values.astype(int)
    y_val = val_df["is_fake"].values.astype(int)
    y_test = test_df["is_fake"].values.astype(int)

    # 2. Pretrained Text Feature Extraction
    logger.info("--- [Step 2/10] Extracting Pretrained Text Representations (MiniLM-L6-v2) ---")
    text_encoder = TextEncoder()

    text_cache_train = os.path.join(cache_dir, "text_embs_train.npy")
    text_cache_val = os.path.join(cache_dir, "text_embs_val.npy")
    text_cache_test = os.path.join(cache_dir, "text_embs_test.npy")

    if os.path.exists(text_cache_train):
        logger.info("Loading cached text embeddings...")
        text_embs_train = np.load(text_cache_train)
        text_embs_val = np.load(text_cache_val)
        text_embs_test = np.load(text_cache_test)
    else:
        logger.info("Computing text embeddings...")
        text_embs_train = text_encoder.encode_batch(train_df["clean_title"].tolist(), batch_size=64)
        text_embs_val = text_encoder.encode_batch(val_df["clean_title"].tolist(), batch_size=64)
        text_embs_test = text_encoder.encode_batch(test_df["clean_title"].tolist(), batch_size=64)

        np.save(text_cache_train, text_embs_train)
        np.save(text_cache_val, text_embs_val)
        np.save(text_cache_test, text_embs_test)

    logger.info(f"Text embeddings shape: {text_embs_train.shape}")

    # 3. Pretrained Vision Feature Extraction
    logger.info("--- [Step 3/10] Extracting Pretrained Vision Representations (ResNet-18) ---")
    vision_encoder = VisionEncoder()

    img_cache_train = os.path.join(cache_dir, "vision_embs_train.npy")
    img_cache_val = os.path.join(cache_dir, "vision_embs_val.npy")
    img_cache_test = os.path.join(cache_dir, "vision_embs_test.npy")

    mask_cache_train = os.path.join(cache_dir, "img_masks_train.npy")
    mask_cache_val = os.path.join(cache_dir, "img_masks_val.npy")
    mask_cache_test = os.path.join(cache_dir, "img_masks_test.npy")

    if os.path.exists(img_cache_train):
        logger.info("Loading cached vision embeddings...")
        vision_embs_train = np.load(img_cache_train)
        vision_embs_val = np.load(img_cache_val)
        vision_embs_test = np.load(img_cache_test)

        img_masks_train = np.load(mask_cache_train)
        img_masks_val = np.load(mask_cache_val)
        img_masks_test = np.load(mask_cache_test)
    else:
        logger.info("Computing vision embeddings...")
        vision_embs_train, img_masks_train = vision_encoder.encode_batch(train_df["image_path"].tolist(), batch_size=32)
        vision_embs_val, img_masks_val = vision_encoder.encode_batch(val_df["image_path"].tolist(), batch_size=32)
        vision_embs_test, img_masks_test = vision_encoder.encode_batch(test_df["image_path"].tolist(), batch_size=32)

        np.save(img_cache_train, vision_embs_train)
        np.save(img_cache_val, vision_embs_val)
        np.save(img_cache_test, vision_embs_test)

        np.save(mask_cache_train, img_masks_train)
        np.save(mask_cache_val, img_masks_val)
        np.save(mask_cache_test, img_masks_test)

    logger.info(f"Vision embeddings shape: {vision_embs_train.shape} (Valid mask sum: {img_masks_train.sum()}/{len(img_masks_train)})")

    # 4. Prompt-Based Text Classification Experiment
    logger.info("--- [Step 4/10] Running Prompt-Based Text Classification Experiment ---")
    prompt_learner = PromptLearner(text_encoder=text_encoder)
    prompt_val_metrics = prompt_learner.calibrate(val_df["clean_title"].tolist(), y_val)

    prompt_feats_train = prompt_learner.extract_prompt_features(train_df["clean_title"].tolist())
    prompt_feats_val = prompt_learner.extract_prompt_features(val_df["clean_title"].tolist())
    prompt_feats_test = prompt_learner.extract_prompt_features(test_df["clean_title"].tolist())

    # Evaluate prompt baseline on test set
    prompt_test_probs = prompt_feats_test[:, 2]
    prompt_test_metrics = compute_comprehensive_metrics(
        y_true=y_test,
        y_prob=prompt_test_probs,
        threshold=prompt_learner.calibrated_threshold,
        model_name="PromptLearning_Baseline"
    )
    logger.info(f"Prompt Learning Test Performance: Acc={prompt_test_metrics['accuracy']}, Macro F1={prompt_test_metrics['macro_f1']}, AUC={prompt_test_metrics['roc_auc']}")

    # 5. Modality Baselines (Text-Only & Image-Only)
    logger.info("--- [Step 5/10] Training Modality Baselines with 5-Fold OOF Probabilities ---")
    text_baseline = TextOnlyBaseline(C=1.0)
    img_baseline = ImageOnlyBaseline(C=1.0)

    # Out-Of-Fold probabilities for training set to prevent leakage
    text_oof_train = text_baseline.compute_oof_predictions(text_embs_train, y_train, n_splits=5)
    img_oof_train = img_baseline.compute_oof_predictions(vision_embs_train, y_train, n_splits=5)

    # Fit baselines on full training split
    text_baseline.fit(text_embs_train, y_train)
    img_baseline.fit(vision_embs_train, y_train)

    text_probs_val = text_baseline.predict_proba(text_embs_val)
    text_probs_test = text_baseline.predict_proba(text_embs_test)

    img_probs_val = img_baseline.predict_proba(vision_embs_val)
    img_probs_test = img_baseline.predict_proba(vision_embs_test)

    text_baseline_test_metrics = compute_comprehensive_metrics(
        y_true=y_test, y_prob=text_probs_test, model_name="TextOnly_Baseline"
    )
    img_baseline_test_metrics = compute_comprehensive_metrics(
        y_true=y_test, y_prob=img_probs_test, model_name="ImageOnly_Baseline"
    )

    logger.info(f"Text-Only Baseline Test: Acc={text_baseline_test_metrics['accuracy']}, Macro F1={text_baseline_test_metrics['macro_f1']}, AUC={text_baseline_test_metrics['roc_auc']}")
    logger.info(f"Image-Only Baseline Test: Acc={img_baseline_test_metrics['accuracy']}, Macro F1={img_baseline_test_metrics['macro_f1']}, AUC={img_baseline_test_metrics['roc_auc']}")

    # 6. Aligned Multimodal Fusion Dataset Construction
    logger.info("--- [Step 6/10] Constructing Aligned Multimodal Fusion Feature Datasets ---")
    feature_aligner = MultimodalFeatureAligner(project_dim=128)

    X_train_fusion, feature_names, feature_schema = feature_aligner.build_fusion_matrix(
        df=train_df,
        text_embs=text_embs_train,
        vision_embs=vision_embs_train,
        img_masks=img_masks_train,
        prompt_feats=prompt_feats_train,
        text_probs=text_oof_train,
        img_probs=img_oof_train,
        is_train=True
    )

    X_val_fusion, _, _ = feature_aligner.build_fusion_matrix(
        df=val_df,
        text_embs=text_embs_val,
        vision_embs=vision_embs_val,
        img_masks=img_masks_val,
        prompt_feats=prompt_feats_val,
        text_probs=text_probs_val,
        img_probs=img_probs_val,
        is_train=False
    )

    X_test_fusion, _, _ = feature_aligner.build_fusion_matrix(
        df=test_df,
        text_embs=text_embs_test,
        vision_embs=vision_embs_test,
        img_masks=img_masks_test,
        prompt_feats=prompt_feats_test,
        text_probs=text_probs_test,
        img_probs=img_probs_test,
        is_train=False
    )

    logger.info(f"Fusion matrices assembled: Train={X_train_fusion.shape}, Val={X_val_fusion.shape}, Test={X_test_fusion.shape}")

    # 7. AutoML Candidate Comparison
    logger.info("--- [Step 7/10] Running AutoML Candidate Architecture Comparison ---")
    automl = AutoMLComparator(random_state=42)
    df_leaderboard = automl.run_comparison(
        X_train=X_train_fusion,
        y_train=y_train,
        X_val=X_val_fusion,
        y_val=y_val
    )
    print("\n" + "="*80)
    print("AutoML CANDIDATE COMPARISON LEADERBOARD (VALIDATION SPLIT)")
    print("="*80)
    print(df_leaderboard.to_string(index=False))
    print("="*80 + "\n")

    # 8. Train and Tune XGBoost Multimodal Fusion Model
    logger.info("--- [Step 8/10] Training and Tuning XGBoost Multimodal Fusion Model ---")
    fusion_model = XGBoostFusionModel(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42
    )
    fusion_model.fit(
        X_train=X_train_fusion,
        y_train=y_train,
        X_val=X_val_fusion,
        y_val=y_val,
        feature_names=feature_names,
        early_stopping_rounds=25
    )

    fusion_test_probs = fusion_model.predict_proba(X_test_fusion)
    fusion_test_metrics = compute_comprehensive_metrics(
        y_true=y_test,
        y_prob=fusion_test_probs,
        model_name="XGBoost_Multimodal_Fusion"
    )

    logger.info(f"XGBoost Fusion Test Performance: Acc={fusion_test_metrics['accuracy']}, Macro F1={fusion_test_metrics['macro_f1']}, AUC={fusion_test_metrics['roc_auc']}")

    # 9. Comparative Benchmarking Summary
    benchmark_dict = {
        "TextOnly_Baseline": text_baseline_test_metrics,
        "ImageOnly_Baseline": img_baseline_test_metrics,
        "PromptLearning_Baseline": prompt_test_metrics,
        "XGBoost_Multimodal_Fusion": fusion_test_metrics
    }
    df_benchmark = build_benchmark_summary(benchmark_dict)

    print("\n" + "="*95)
    print("FINAL TEST SET BENCHMARK COMPARISON (HELD-OUT PUBLIC TEST SPLIT)")
    print("="*95)
    print(df_benchmark.to_string(index=False))
    print("="*95 + "\n")

    # 10. SHAP Explanations
    logger.info("--- [Step 9/10] Computing SHAP TreeExplainer Global and Local Explanations ---")
    shap_explainer = MultimodalSHAPExplainer(fusion_model.model, feature_names)

    # Use 200 background test samples for global SHAP calculation
    eval_indices = np.random.RandomState(42).choice(len(X_test_fusion), size=min(200, len(X_test_fusion)), replace=False)
    global_shap = shap_explainer.compute_global_explanations(X_test_fusion[eval_indices], top_k=25)

    print("\nTOP 10 GLOBAL MULTIMODAL FEATURES (SHAP TREE-EXPLAINER):")
    for item in global_shap["top_global_features"][:10]:
        print(f"  Rank {item['rank']:2d}: {item['feature']:<30} (Mean |SHAP| = {item['mean_abs_shap']:.5f})")

    # Local sample explanations for representative test items
    local_explanations = []
    # Pick a few high-confidence Fake and high-confidence Real samples
    fake_indices = np.where((y_test == 1) & (fusion_test_probs > 0.8))[0][:3]
    real_indices = np.where((y_test == 0) & (fusion_test_probs < 0.2))[0][:3]

    for idx in list(fake_indices) + list(real_indices):
        row = test_df.iloc[idx]
        local_exp = shap_explainer.explain_sample(
            x_vector=X_test_fusion[idx],
            sample_metadata={
                "id": str(row["id"]),
                "ground_truth": "Fake" if y_test[idx] == 1 else "Real",
                "clean_title": str(row["clean_title"]),
                "fakeddit_6_way": int(row["fakeddit_6_way_label"]),
                "image_path": str(row["image_path"])
            },
            top_k=5
        )
        local_explanations.append(local_exp)

    shap_summary_artifact = {
        "global_explanations": global_shap,
        "sample_local_explanations": local_explanations
    }

    # 11. Artifact Management and Versioned Persistence
    logger.info("--- [Step 10/10] Persisting Versioned Model Artifacts and Schemas ---")

    # Save models
    fusion_model.save(version_dir)
    joblib.dump(text_baseline, os.path.join(version_dir, "text_baseline.joblib"))
    joblib.dump(img_baseline, os.path.join(version_dir, "image_baseline.joblib"))

    # Save PCA projectors
    joblib.dump(feature_aligner.text_pca, os.path.join(version_dir, "text_pca.joblib"))
    joblib.dump(feature_aligner.vision_pca, os.path.join(version_dir, "vision_pca.joblib"))

    # Save schemas and configs
    artifact_manager.save_json(version, "feature_schema.json", feature_schema)
    artifact_manager.save_json(version, "preprocessing_config.json", {
        "text_model": text_encoder.model_name,
        "vision_backbone": "resnet18_imagenet",
        "image_dimension": 224,
        "prompt_template": prompt_learner.template,
        "project_dim": 128
    })

    # Save metrics and comparisons
    artifact_manager.save_json(version, "metrics.json", benchmark_dict)
    artifact_manager.save_json(version, "candidate_comparison.json", {
        "selection_metric": "val_macro_f1",
        "winning_candidate": automl.best_candidate_name,
        "leaderboard": automl.leaderboard
    })
    artifact_manager.save_json(version, "shap_summary.json", shap_summary_artifact)

    # Save label schema
    with open("config/dataset_config.json", "r") as f:
        ds_cfg = json.load(f)
    artifact_manager.save_json(version, "label_mapping.json", ds_cfg["label_schema"])

    # Copy data profile to version directory
    if os.path.exists(os.path.join(processed_dir, "data_profile.json")):
        with open(os.path.join(processed_dir, "data_profile.json"), "r") as f:
            dprof = json.load(f)
        artifact_manager.save_json(version, "data_profile.json", dprof)

    # Save held-out test predictions
    test_pred_records = []
    for idx in range(min(500, len(test_df))):
        test_pred_records.append({
            "id": str(test_df.iloc[idx]["id"]),
            "clean_title": str(test_df.iloc[idx]["clean_title"]),
            "ground_truth_label": int(y_test[idx]),
            "ground_truth_veracity": "Fake" if y_test[idx] == 1 else "Real",
            "predicted_label": int(fusion_test_probs[idx] >= 0.5),
            "predicted_veracity": "Fake" if fusion_test_probs[idx] >= 0.5 else "Real",
            "fake_probability": round(float(fusion_test_probs[idx]), 4),
            "text_baseline_fake_prob": round(float(text_probs_test[idx]), 4),
            "image_baseline_fake_prob": round(float(img_probs_test[idx]), 4),
            "prompt_fake_prob": round(float(prompt_test_probs[idx]), 4)
        })
    artifact_manager.save_json(version, "held_out_test_predictions.json", test_pred_records)

    # Create manifest
    manifest = {
        "model_version": version,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "winning_candidate": automl.best_candidate_name,
        "test_macro_f1": fusion_test_metrics["macro_f1"],
        "test_roc_auc": fusion_test_metrics["roc_auc"],
        "test_accuracy": fusion_test_metrics["accuracy"],
        "total_features": len(feature_names),
        "artifacts_packaged": [
            "fusion_model.joblib",
            "fusion_model.json",
            "text_baseline.joblib",
            "image_baseline.joblib",
            "text_pca.joblib",
            "vision_pca.joblib",
            "feature_schema.json",
            "preprocessing_config.json",
            "metrics.json",
            "candidate_comparison.json",
            "data_profile.json",
            "shap_summary.json",
            "label_mapping.json",
            "held_out_test_predictions.json"
        ]
    }
    artifact_manager.save_manifest(version, manifest)

    # Integrity validation
    integrity = artifact_manager.validate_version_integrity(version)
    logger.info(f"Artifact integrity validation: {integrity['all_artifacts_present']}")

    logger.info("========== PHASE 3 TRAINING PIPELINE COMPLETED SUCCESSFULLY! ==========")


if __name__ == "__main__":
    main()
