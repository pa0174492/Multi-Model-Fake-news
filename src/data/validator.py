"""
Dataset Validation and Profiling Module for Fakeddit Multimodal Fake News.

Validates schema, text modality, image modality, label mappings, and enforces
strict cross-split leakage prevention (zero ID and text duplicate overlap).
"""

import os
import re
import json
import logging
from typing import Dict, List, Tuple, Set, Optional, Any
import pandas as pd
from PIL import Image

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "id",
    "clean_title",
    "image_url",
    "hasImage",
    "2_way_label",
    "3_way_label",
    "6_way_label"
]

# Canonical task mapping definition:
# Fakeddit raw 2_way_label: 1 = Real, 0 = Fake
# Target binary is_fake: 0 = Real, 1 = Fake
TASK_LABEL_MAPPING = {
    "task": "Multimodal Fake News Detection",
    "fakeddit_2_way_to_is_fake": {
        1: 0,  # Fakeddit 1 (Real) -> is_fake = 0
        0: 1   # Fakeddit 0 (Fake) -> is_fake = 1
    },
    "canonical_classes": {
        0: "Real News",
        1: "Fake News"
    },
    "fakeddit_6_way_definitions": {
        0: "True",
        1: "Satire / Parody",
        2: "Misleading Content",
        3: "Manipulated Content",
        4: "False Connection",
        5: "Completely Fabricated"
    }
}


class DatasetValidator:
    """
    Validates multimodal samples, detects cross-split leakage, and tracks exclusion reasons.
    """

    def __init__(self, min_title_chars: int = 5, min_title_words: int = 2, min_img_dim: int = 32):
        self.min_title_chars = min_title_chars
        self.min_title_words = min_title_words
        self.min_img_dim = min_img_dim

    def validate_schema(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Verifies that all required columns are present."""
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        return len(missing) == 0, missing

    def validate_text(self, text: Any) -> Tuple[bool, str]:
        """Validates textual headline quality."""
        if pd.isna(text) or text is None:
            return False, "NULL_TEXT"
        text_str = str(text).strip()
        if len(text_str) < self.min_title_chars:
            return False, "TEXT_TOO_SHORT_CHARS"
        words = text_str.split()
        if len(words) < self.min_title_words:
            return False, "TEXT_TOO_SHORT_WORDS"
        return True, "VALID"

    def validate_image_file(self, image_path: str) -> Tuple[bool, str]:
        """Verifies that the downloaded image file is uncorrupted and of valid dimension."""
        if not os.path.exists(image_path):
            return False, "IMAGE_FILE_NOT_FOUND"
        try:
            with Image.open(image_path) as img:
                img.verify()
            # Re-open for dimension inspection after verify()
            with Image.open(image_path) as img:
                w, h = img.size
                if w < self.min_img_dim or h < self.min_img_dim:
                    return False, f"IMAGE_TOO_SMALL_{w}x{h}"
            return True, "VALID"
        except Exception as e:
            return False, f"IMAGE_CORRUPTED_{type(e).__name__}"

    def validate_labels(self, row: pd.Series) -> Tuple[bool, str, Optional[int]]:
        """
        Validates Fakeddit label consistency and computes the canonical task label.
        Returns: (is_valid, reason, is_fake_target)
        """
        try:
            two_way = int(row["2_way_label"])
            six_way = int(row["6_way_label"])
            three_way = int(row["3_way_label"])
        except (ValueError, TypeError):
            return False, "NON_NUMERIC_LABEL", None

        if two_way not in (0, 1):
            return False, f"INVALID_2_WAY_LABEL_{two_way}", None
        if six_way not in range(6):
            return False, f"INVALID_6_WAY_LABEL_{six_way}", None
        if three_way not in range(3):
            return False, f"INVALID_3_WAY_LABEL_{three_way}", None

        # Cross-label consistency check:
        # In Fakeddit, six_way==0 MUST have two_way==1 (Real)
        if six_way == 0 and two_way != 1:
            return False, "INCONSISTENT_REAL_LABEL", None
        if six_way > 0 and two_way != 0:
            return False, "INCONSISTENT_FAKE_LABEL", None

        # Compute canonical task label: is_fake (0=Real, 1=Fake)
        is_fake = TASK_LABEL_MAPPING["fakeddit_2_way_to_is_fake"][two_way]
        return True, "VALID", is_fake

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalized string for deduplication."""
        text = str(text).lower().strip()
        text = re.sub(r'[^\w\s]', '', text)
        return " ".join(text.split())

    def check_cross_split_leakage(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Checks for ID overlaps and normalized text headline overlaps across splits.
        """
        train_ids = set(train_df["id"].dropna().astype(str))
        val_ids = set(val_df["id"].dropna().astype(str))
        test_ids = set(test_df["id"].dropna().astype(str))

        id_leakage = {
            "train_val_overlap_count": len(train_ids.intersection(val_ids)),
            "train_test_overlap_count": len(train_ids.intersection(test_ids)),
            "val_test_overlap_count": len(val_ids.intersection(test_ids)),
        }

        # Check headline text duplicates across splits
        train_texts = set(train_df["clean_title"].dropna().apply(self.normalize_text))
        val_texts = set(val_df["clean_title"].dropna().apply(self.normalize_text))
        test_texts = set(test_df["clean_title"].dropna().apply(self.normalize_text))

        text_leakage = {
            "train_val_duplicate_texts": len(train_texts.intersection(val_texts)),
            "train_test_duplicate_texts": len(train_texts.intersection(test_texts)),
            "val_test_duplicate_texts": len(val_texts.intersection(test_texts)),
        }

        has_leakage = any(v > 0 for v in id_leakage.values()) or any(v > 0 for v in text_leakage.values())

        return {
            "id_leakage": id_leakage,
            "text_duplicate_leakage": text_leakage,
            "clean_splits_verified": not has_leakage
        }
