"""
Unit Tests for Inference Pipeline, SHAP Explainer, and Artifact Validation.
"""

import os
import unittest
import numpy as np

from src.inference.pipeline import MultimodalInferencePipeline
from src.artifacts.artifact_manager import ArtifactManager


class TestInferencePipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.version = "v1.0.0"
        cls.artifact_manager = ArtifactManager()
        cls.pipeline = MultimodalInferencePipeline(version=cls.version)
        cls.pipeline.load()

    def test_artifact_integrity(self):
        status = self.artifact_manager.validate_version_integrity(self.version)
        self.assertTrue(status["all_artifacts_present"])
        for file_name, exists in status["files"].items():
            self.assertTrue(exists, f"Missing artifact: {file_name}")

    def test_pipeline_prediction(self):
        result = self.pipeline.predict(
            text="Breaking: Scientific discovery confirms water ice on the Moon",
            image_path=None,  # test missing image fallback
            metadata={"score": 100, "num_comments": 20, "upvote_ratio": 0.9}
        )
        self.assertIn("prediction", result)
        self.assertIn("fake_probability", result)
        self.assertIn("confidence", result)
        self.assertIn("modality_scores", result)
        self.assertIn(result["prediction"], ["Real", "Fake"])
        self.assertGreaterEqual(result["fake_probability"], 0.0)
        self.assertLessEqual(result["fake_probability"], 1.0)

    def test_pipeline_explanation(self):
        explanation = self.pipeline.explain(
            text="Unbelievable scandal exposed in shocking viral video",
            image_path=None,
            metadata={"score": 5, "num_comments": 0, "upvote_ratio": 0.4},
            top_k=3
        )
        self.assertIn("prediction", explanation)
        self.assertIn("top_positive_contributors_fake", explanation)
        self.assertIn("top_negative_contributors_real", explanation)
        self.assertLessEqual(len(explanation["top_positive_contributors_fake"]), 3)


if __name__ == "__main__":
    unittest.main()
