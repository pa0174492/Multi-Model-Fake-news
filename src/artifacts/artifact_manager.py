"""
Artifact Management and Versioning System.

Manages versioned storage, retrieval, and validation of models, feature schemas,
preprocessing configurations, evaluation metrics, and explanation metadata.
"""

import os
import json
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_ROOT = "artifacts"


class ArtifactManager:
    """Manages versioned ML artifacts."""

    def __init__(self, root_dir: str = DEFAULT_ARTIFACT_ROOT):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def get_version_dir(self, version: str) -> str:
        return os.path.join(self.root_dir, version)

    def save_manifest(self, version: str, manifest_data: Dict[str, Any]):
        v_dir = self.get_version_dir(version)
        os.makedirs(v_dir, exist_ok=True)
        manifest_path = os.path.join(v_dir, "artifact_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)

    def save_json(self, version: str, filename: str, data: Any):
        v_dir = self.get_version_dir(version)
        os.makedirs(v_dir, exist_ok=True)
        file_path = os.path.join(v_dir, filename)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_json(self, version: str, filename: str) -> Any:
        file_path = os.path.join(self.get_version_dir(version), filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Artifact {filename} not found in version {version}")
        with open(file_path, "r") as f:
            return json.load(f)

    def list_versions(self) -> List[str]:
        if not os.path.exists(self.root_dir):
            return []
        return sorted([d for d in os.listdir(self.root_dir) if os.path.isdir(os.path.join(self.root_dir, d))])

    def validate_version_integrity(self, version: str) -> Dict[str, Any]:
        """Verifies that all required artifact files exist for this version."""
        v_dir = self.get_version_dir(version)
        required_files = [
            "fusion_model.joblib",
            "text_baseline.joblib",
            "image_baseline.joblib",
            "feature_schema.json",
            "preprocessing_config.json",
            "metrics.json",
            "candidate_comparison.json",
            "data_profile.json",
            "shap_summary.json",
            "label_mapping.json"
        ]

        file_status = {}
        all_present = True

        for fname in required_files:
            path = os.path.join(v_dir, fname)
            present = os.path.exists(path) and os.path.getsize(path) > 0
            file_status[fname] = present
            if not present:
                all_present = False

        return {
            "version": version,
            "version_directory": v_dir,
            "all_artifacts_present": all_present,
            "files": file_status
        }
