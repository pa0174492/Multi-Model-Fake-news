"""
Inference Demonstration and Held-Out Verification Script.

Tests the versioned MultimodalInferencePipeline (v1.0.0) on held-out samples,
validating predictions, confidence scores, and SHAP local explanations.
"""

import os
import sys

sys.path.insert(0, os.path.abspath("."))

import json
import logging
import pandas as pd
from src.inference.pipeline import MultimodalInferencePipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Initializing versioned inference pipeline 'v1.0.0'...")
    pipeline = MultimodalInferencePipeline(artifact_root="artifacts", version="v1.0.0")
    pipeline.load()

    # Load held-out test dataset
    test_df = pd.read_csv("data/processed/test_multimodal.csv")
    logger.info(f"Loaded held-out test dataset ({len(test_df)} samples).")

    # Select representative samples: one Real, one Fake
    sample_real = test_df[test_df["is_fake"] == 0].iloc[0]
    sample_fake = test_df[test_df["is_fake"] == 1].iloc[0]

    demo_samples = [("REAL_SAMPLE_1", sample_real), ("FAKE_SAMPLE_1", sample_fake)]

    print("\n" + "="*85)
    print("DEMONSTRATION: MULTIMODAL INFERENCE AND SHAP EXPLANATION PIPELINE (v1.0.0)")
    print("="*85)

    for tag, sample in demo_samples:
        title = sample["clean_title"]
        img_path = sample["image_path"]
        meta = {
            "score": float(sample.get("score", 0)),
            "num_comments": float(sample.get("num_comments", 0)),
            "upvote_ratio": float(sample.get("upvote_ratio", 0.5))
        }

        print(f"\n--- Testing Sample: {tag} [{sample['id']}] ---")
        print(f"Headline:        \"{title}\"")
        print(f"Image Path:      {img_path} (Exists: {os.path.exists(img_path)})")
        print(f"Ground Truth:    {sample['veracity_label']} (Fakeddit 6-way: {sample['fakeddit_6_way_label']})")
        print(f"Reddit Metadata: Score={meta['score']}, Comments={meta['num_comments']}, UpvoteRatio={meta['upvote_ratio']}")

        # Predict
        pred_result = pipeline.predict(title, img_path, meta)
        print(f"Prediction:      {pred_result['prediction']} (Fake Prob: {pred_result['fake_probability']:.4f}, Confidence: {pred_result['confidence']:.4f})")
        print("Modality Baselines:")
        for k, v in pred_result["modality_scores"].items():
            print(f"  - {k}: {v}")

        # Explain
        explanation = pipeline.explain(title, img_path, meta, top_k=3)
        print("SHAP Local Explanation (Top Positive Contributors to Fake):")
        for item in explanation["top_positive_contributors_fake"]:
            print(f"  [+] {item['feature']:<28} value={item['feature_value']:<8.4f} SHAP={item['shap_value']:+.4f}")
        print("SHAP Local Explanation (Top Negative Contributors to Real):")
        for item in explanation["top_negative_contributors_real"]:
            print(f"  [-] {item['feature']:<28} value={item['feature_value']:<8.4f} SHAP={item['shap_value']:+.4f}")

    # Test Missing Modality Robustness (Headline only, image missing)
    print("\n--- Testing Robustness: Missing Image Modality Fallback ---")
    robustness_result = pipeline.predict(
        text="Breaking: Unverified claim posted without accompanying visual evidence",
        image_path="non_existent_image.jpg",
        metadata={"score": 10, "num_comments": 2, "upvote_ratio": 0.5}
    )
    print(f"Missing Image Result: {robustness_result['prediction']} (Fake Prob: {robustness_result['fake_probability']:.4f}, Valid Image Mask: {robustness_result['modality_scores']['has_valid_image']})")

    print("="*85 + "\n")
    logger.info("Inference demonstration completed successfully!")


if __name__ == "__main__":
    main()
