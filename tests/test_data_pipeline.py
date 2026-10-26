"""
Unit Tests for Data Pipeline, Validator, and Leakage Prevention.
"""

import os
import unittest
import pandas as pd
import numpy as np

from src.data.validator import DatasetValidator, TASK_LABEL_MAPPING


class TestDataPipeline(unittest.TestCase):

    def setUp(self):
        self.validator = DatasetValidator(min_title_chars=5, min_title_words=2)

    def test_schema_validation(self):
        valid_df = pd.DataFrame(columns=[
            "id", "clean_title", "image_url", "hasImage",
            "2_way_label", "3_way_label", "6_way_label"
        ])
        is_valid, missing = self.validator.validate_schema(valid_df)
        self.assertTrue(is_valid)
        self.assertEqual(len(missing), 0)

        invalid_df = pd.DataFrame(columns=["id", "clean_title"])
        is_valid, missing = self.validator.validate_schema(invalid_df)
        self.assertFalse(is_valid)
        self.assertIn("image_url", missing)

    def test_label_mappings(self):
        # Real sample: 2_way=1, 3_way=0, 6_way=0
        real_row = pd.Series({"2_way_label": 1, "3_way_label": 0, "6_way_label": 0})
        ok, reason, is_fake = self.validator.validate_labels(real_row)
        self.assertTrue(ok)
        self.assertEqual(is_fake, 0)  # Canonical 0 = Real

        # Fake sample: 2_way=0, 3_way=2, 6_way=4
        fake_row = pd.Series({"2_way_label": 0, "3_way_label": 2, "6_way_label": 4})
        ok, reason, is_fake = self.validator.validate_labels(fake_row)
        self.assertTrue(ok)
        self.assertEqual(is_fake, 1)  # Canonical 1 = Fake

        # Inconsistent label: 6_way=0 but 2_way=0
        bad_row = pd.Series({"2_way_label": 0, "3_way_label": 0, "6_way_label": 0})
        ok, reason, _ = self.validator.validate_labels(bad_row)
        self.assertFalse(ok)
        self.assertEqual(reason, "INCONSISTENT_REAL_LABEL")

    def test_text_validation(self):
        self.assertTrue(self.validator.validate_text("Breaking news headline")[0])
        self.assertFalse(self.validator.validate_text("")[0])
        self.assertFalse(self.validator.validate_text("Hi")[0])

    def test_cross_split_leakage_check(self):
        train = pd.DataFrame({"id": ["a", "b"], "clean_title": ["News 1", "News 2"]})
        val = pd.DataFrame({"id": ["c", "d"], "clean_title": ["News 3", "News 4"]})
        test = pd.DataFrame({"id": ["e", "f"], "clean_title": ["News 5", "News 6"]})

        leakage = self.validator.check_cross_split_leakage(train, val, test)
        self.assertTrue(leakage["clean_splits_verified"])

        # Inject leakage
        leak_test = pd.DataFrame({"id": ["a", "z"], "clean_title": ["News 1", "News 9"]})
        leakage_detected = self.validator.check_cross_split_leakage(train, val, leak_test)
        self.assertFalse(leakage_detected["clean_splits_verified"])
        self.assertEqual(leakage_detected["id_leakage"]["train_test_overlap_count"], 1)


if __name__ == "__main__":
    unittest.main()
