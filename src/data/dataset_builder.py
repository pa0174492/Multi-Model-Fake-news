"""
Multimodal Dataset Builder for Fakeddit.

Samples balanced, complete text-image pairs across train, validation, and test splits.
Downloads and verifies images in parallel, tracks exclusions, avoids data leakage,
and creates clean processed splits.
"""

import os
import io
import json
import logging
import urllib.request
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from PIL import Image

from src.data.validator import DatasetValidator, TASK_LABEL_MAPPING

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def download_single_image(url: str, out_path: str, timeout: int = 5) -> Tuple[bool, str]:
    """Downloads and verifies an image file using PIL."""
    if not url or not str(url).startswith("http"):
        return False, "INVALID_URL"
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        try:
            with Image.open(out_path) as img:
                img.verify()
            return True, "ALREADY_EXISTS"
        except Exception:
            pass

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        
        # Verify with PIL before saving
        img = Image.open(io.BytesIO(data))
        img.verify()

        # Save to disk as RGB JPEG for consistency
        img = Image.open(io.BytesIO(data)).convert("RGB")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path, format="JPEG", quality=90)
        return True, "SUCCESS"
    except urllib.error.HTTPError as e:
        return False, f"HTTP_{e.code}"
    except urllib.error.URLError as e:
        return False, f"URL_ERROR_{type(e.reason).__name__}"
    except Exception as e:
        return False, f"CORRUPT_{type(e).__name__}"


class MultimodalDatasetBuilder:
    """
    Builds clean, balanced multimodal subsets with complete text and image modalities.
    """

    def __init__(
        self,
        raw_train_path: str = "data/raw/multimodal_train.tsv",
        raw_val_path: str = "data/raw/multimodal_validate.tsv",
        raw_test_path: str = "data/raw/multimodal_test_public.tsv",
        output_dir: str = "data/processed",
        images_dir: str = "data/images",
        max_workers: int = 16
    ):
        self.raw_paths = {
            "train": raw_train_path,
            "val": raw_val_path,
            "test": raw_test_path
        }
        self.output_dir = output_dir
        self.images_dir = images_dir
        self.max_workers = max_workers
        self.validator = DatasetValidator()
        self.exclusion_log: Dict[str, Dict[str, int]] = {"train": {}, "val": {}, "test": {}}

    def build_split(
        self,
        split_name: str,
        target_count: int,
        seen_ids: set,
        seen_texts: set
    ) -> pd.DataFrame:
        """
        Builds a single split with target_count verified multimodal samples.
        Maintains ~50/50 balance between real (is_fake=0) and fake (is_fake=1).
        """
        raw_path = self.raw_paths[split_name]
        logger.info(f"Loading raw {split_name} split from {raw_path}...")
        df_raw = pd.read_csv(raw_path, sep="\t")

        valid_schema, missing_cols = self.validator.validate_schema(df_raw)
        if not valid_schema:
            raise ValueError(f"Raw {split_name} dataset is missing columns: {missing_cols}")

        target_per_class = target_count // 2
        collected_samples: List[Dict[str, Any]] = []
        counts = {0: 0, 1: 0}  # 0: Real, 1: Fake

        split_img_dir = os.path.join(self.images_dir, split_name)
        os.makedirs(split_img_dir, exist_ok=True)

        logger.info(f"Scanning candidates for {split_name} (target={target_count}, {target_per_class}/class)...")

        # Shuffle candidates deterministically
        df_shuffled = df_raw.sample(frac=1.0, random_state=42).reset_index(drop=True)

        candidate_batch = []
        for idx, row in df_shuffled.iterrows():
            item_id = str(row["id"])
            if item_id in seen_ids:
                self._record_exclusion(split_name, "LEAKAGE_DUPLICATE_ID")
                continue

            text_str = str(row.get("clean_title", ""))
            text_norm = self.validator.normalize_text(text_str)
            if text_norm in seen_texts:
                self._record_exclusion(split_name, "LEAKAGE_DUPLICATE_TEXT")
                continue

            text_ok, text_reason = self.validator.validate_text(text_str)
            if not text_ok:
                self._record_exclusion(split_name, text_reason)
                continue

            label_ok, label_reason, is_fake = self.validator.validate_labels(row)
            if not label_ok or is_fake is None:
                self._record_exclusion(split_name, label_reason)
                continue

            # Check if this class quota is already met
            if counts[is_fake] >= target_per_class:
                continue

            img_url = str(row.get("image_url", ""))
            if not img_url.startswith("http"):
                self._record_exclusion(split_name, "MISSING_IMAGE_URL")
                continue

            out_img_path = os.path.join(split_img_dir, f"{item_id}.jpg")
            candidate_batch.append((row, item_id, text_norm, is_fake, img_url, out_img_path))

            # When we have enough candidates buffered, download in parallel
            if len(candidate_batch) >= (target_count - len(collected_samples)) * 2:
                break

        # Parallel download of image candidates
        logger.info(f"Downloading images for {len(candidate_batch)} candidates with {self.max_workers} threads...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_cand = {
                executor.submit(download_single_image, cand[4], cand[5]): cand
                for cand in candidate_batch
            }

            for future in as_completed(future_to_cand):
                cand = future_to_cand[future]
                row, item_id, text_norm, is_fake, img_url, out_img_path = cand

                if counts[is_fake] >= target_per_class:
                    continue

                success, reason = future.result()
                if not success:
                    self._record_exclusion(split_name, f"IMAGE_FETCH_{reason}")
                    continue

                # Validate image file integrity
                img_ok, img_reason = self.validator.validate_image_file(out_img_path)
                if not img_ok:
                    self._record_exclusion(split_name, img_reason)
                    if os.path.exists(out_img_path):
                        os.remove(out_img_path)
                    continue

                # Add sample
                seen_ids.add(item_id)
                seen_texts.add(text_norm)
                counts[is_fake] += 1

                collected_samples.append({
                    "id": item_id,
                    "clean_title": str(row["clean_title"]).strip(),
                    "image_path": out_img_path,
                    "image_url": img_url,
                    "fakeddit_2_way_label": int(row["2_way_label"]),
                    "fakeddit_3_way_label": int(row["3_way_label"]),
                    "fakeddit_6_way_label": int(row["6_way_label"]),
                    "is_fake": is_fake,
                    "veracity_label": "Fake" if is_fake == 1 else "Real",
                    "subreddit": str(row.get("subreddit", "unknown")),
                    "score": float(row.get("score", 0)),
                    "num_comments": float(row.get("num_comments", 0)),
                    "upvote_ratio": float(row.get("upvote_ratio", 0.5)),
                    "split": split_name
                })

                if len(collected_samples) >= target_count:
                    break

        split_df = pd.DataFrame(collected_samples)
        logger.info(f"Split {split_name} completed: {len(split_df)} samples. Class counts: {split_df['is_fake'].value_counts().to_dict()}")
        return split_df

    def _record_exclusion(self, split: str, reason: str):
        self.exclusion_log[split][reason] = self.exclusion_log[split].get(reason, 0) + 1

    def build_all(self, train_target: int = 5000, val_target: int = 1000, test_target: int = 1000) -> Dict[str, pd.DataFrame]:
        """
        Builds train, validation, and test splits with strict cross-split deduplication.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        seen_ids: set = set()
        seen_texts: set = set()

        # Build test split first to protect held-out test distribution
        test_df = self.build_split("test", test_target, seen_ids, seen_texts)
        # Build validation split second
        val_df = self.build_split("val", val_target, seen_ids, seen_texts)
        # Build train split third
        train_df = self.build_split("train", train_target, seen_ids, seen_texts)

        # Verify no leakage
        leakage_check = self.validator.check_cross_split_leakage(train_df, val_df, test_df)
        logger.info(f"Cross-split leakage check: {leakage_check}")

        # Save processed splits
        train_path = os.path.join(self.output_dir, "train_multimodal.csv")
        val_path = os.path.join(self.output_dir, "val_multimodal.csv")
        test_path = os.path.join(self.output_dir, "test_multimodal.csv")

        train_df.to_csv(train_path, index=False)
        val_df.to_csv(val_path, index=False)
        test_df.to_csv(test_path, index=False)

        # Save data profile
        profile = {
            "dataset": "Fakeddit Multimodal Benchmark",
            "splits": {
                "train": {
                    "count": len(train_df),
                    "class_distribution": train_df["is_fake"].value_counts().to_dict(),
                    "veracity_distribution": train_df["veracity_label"].value_counts().to_dict(),
                    "fakeddit_6_way_distribution": train_df["fakeddit_6_way_label"].value_counts().to_dict(),
                    "file_path": train_path
                },
                "val": {
                    "count": len(val_df),
                    "class_distribution": val_df["is_fake"].value_counts().to_dict(),
                    "veracity_distribution": val_df["veracity_label"].value_counts().to_dict(),
                    "fakeddit_6_way_distribution": val_df["fakeddit_6_way_label"].value_counts().to_dict(),
                    "file_path": val_path
                },
                "test": {
                    "count": len(test_df),
                    "class_distribution": test_df["is_fake"].value_counts().to_dict(),
                    "veracity_distribution": test_df["veracity_label"].value_counts().to_dict(),
                    "fakeddit_6_way_distribution": test_df["fakeddit_6_way_label"].value_counts().to_dict(),
                    "file_path": test_path
                }
            },
            "total_multimodal_samples": len(train_df) + len(val_df) + len(test_df),
            "leakage_verification": leakage_check,
            "exclusion_log": self.exclusion_log,
            "label_schema": TASK_LABEL_MAPPING
        }

        profile_path = os.path.join(self.output_dir, "data_profile.json")
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=2)

        logger.info(f"Data profile saved to {profile_path}")
        return {"train": train_df, "val": val_df, "test": test_df}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Multimodal Fakeddit Dataset")
    parser.add_argument("--train-target", type=int, default=5000)
    parser.add_argument("--val-target", type=int, default=1000)
    parser.add_argument("--test-target", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    builder = MultimodalDatasetBuilder(max_workers=args.workers)
    builder.build_all(
        train_target=args.train_target,
        val_target=args.val_target,
        test_target=args.test_target
    )
