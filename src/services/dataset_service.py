"""
Dataset and Corpus Service for Fakeddit and Multimodal Benchmarks.
Provides fast search, pagination, split filtering, schema metadata, and dataset profiling.
"""

import os
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.abspath("."), "data", "processed")
IMAGES_DIR = os.path.join(os.path.abspath("."), "data", "images")

# Fine-grained Fakeddit 6-way label descriptions
FAKEDDIT_6WAY_LABELS = {
    0: "True / Real Authentic News",
    1: "Satire / Parody (Humorous & Fabricated)",
    2: "Misleading Content (Distorted Context)",
    3: "Manipulated Content (Altered / Photoshopped)",
    4: "False Connection (Clickbait / Mismatched Caption)",
    5: "Imposter Content (Fabricated Attribution)"
}


class DatasetService:
    """Manages reading, caching, querying, and profiling the Fakeddit multimodal dataset."""

    def __init__(self):
        self._dfs: Dict[str, pd.DataFrame] = {}
        self._summary_cache: Optional[Dict[str, Any]] = None
        self._is_loaded = False

    def _ensure_loaded(self):
        if not self._is_loaded:
            self._load_datasets()
            self._is_loaded = True

    def _load_datasets(self):
        """Loads and indexes the train, val, and test split CSVs."""
        for split in ["train", "val", "test"]:
            csv_path = os.path.join(DATA_DIR, f"{split}_multimodal.csv")
            if os.path.exists(csv_path):
                try:
                    df = pd.read_csv(csv_path)
                    # Normalize columns if needed
                    df["split"] = split
                    self._dfs[split] = df
                    logger.info(f"Loaded {split} split: {len(df)} samples")
                except Exception as e:
                    logger.warning(f"Failed to load {split} dataset: {e}")

    def get_dataset_summary(self) -> Dict[str, Any]:
        """Returns comprehensive dataset statistics, class balance, and schema dictionary."""
        self._ensure_loaded()
        if self._summary_cache:
            return self._summary_cache

        total_samples = sum(len(df) for df in self._dfs.values())
        split_counts = {split: len(df) for split, df in self._dfs.items()}

        all_df = pd.concat(list(self._dfs.values()), ignore_index=True) if self._dfs else pd.DataFrame()

        if all_df.empty:
            return {"total_samples": 0, "splits": {}}

        # Binary label counts
        real_count = int((all_df["is_fake"] == 0).sum())
        fake_count = int((all_df["is_fake"] == 1).sum())

        # Fine-grained 6-way distribution
        six_way_counts = {}
        if "fakeddit_6_way_label" in all_df.columns:
            val_counts = all_df["fakeddit_6_way_label"].value_counts().to_dict()
            for lbl_idx, count in val_counts.items():
                lbl_name = FAKEDDIT_6WAY_LABELS.get(int(lbl_idx), f"Class {lbl_idx}")
                six_way_counts[lbl_name] = int(count)

        # Top subreddits
        top_subreddits = {}
        if "subreddit" in all_df.columns:
            top_subreddits = all_df["subreddit"].value_counts().head(10).to_dict()

        # Engagement stats
        avg_score = float(all_df["score"].mean()) if "score" in all_df.columns else 0.0
        avg_comments = float(all_df["num_comments"].mean()) if "num_comments" in all_df.columns else 0.0
        avg_upvote_ratio = float(all_df["upvote_ratio"].mean()) if "upvote_ratio" in all_df.columns else 0.0

        schema_dict = [
            {"column": "id", "type": "String", "description": "Unique Reddit submission identifier"},
            {"column": "clean_title", "type": "Text", "description": "Preprocessed headline text (URLs, Markdown & symbols removed)"},
            {"column": "is_fake", "type": "Integer (0/1)", "description": "Binary ground-truth (0 = Real News, 1 = Fake News)"},
            {"column": "fakeddit_2_way_label", "type": "Integer (0/1)", "description": "Official 2-way Fakeddit classification label"},
            {"column": "fakeddit_6_way_label", "type": "Integer (0-5)", "description": "Fine-grained taxonomy (Satire, Misleading, Imposter, etc.)"},
            {"column": "veracity_label", "type": "String", "description": "Human-readable label name ('real' vs 'fake')"},
            {"column": "subreddit", "type": "String", "description": "Originating Reddit subreddit community"},
            {"column": "score", "type": "Integer", "description": "Reddit submission engagement score (upvotes minus downvotes)"},
            {"column": "num_comments", "type": "Integer", "description": "Number of public discussions/comments on post"},
            {"column": "upvote_ratio", "type": "Float (0.0-1.0)", "description": "Ratio of positive upvotes among all votes"},
            {"column": "split", "type": "Categorical", "description": "Split assignment ('train', 'val', 'test') with zero leakage"}
        ]

        self._summary_cache = {
            "total_samples": total_samples,
            "splits": split_counts,
            "class_distribution": {
                "real_samples": real_count,
                "fake_samples": fake_count,
                "real_percentage": round((real_count / total_samples) * 100, 2) if total_samples else 0,
                "fake_percentage": round((fake_count / total_samples) * 100, 2) if total_samples else 0
            },
            "six_way_taxonomy": six_way_counts,
            "top_subreddits": top_subreddits,
            "engagement_averages": {
                "mean_score": round(avg_score, 1),
                "mean_comments": round(avg_comments, 1),
                "mean_upvote_ratio": round(avg_upvote_ratio, 3)
            },
            "schema": schema_dict
        }
        return self._summary_cache

    def query_dataset(
        self,
        split: str = "all",
        query_text: Optional[str] = None,
        veracity_filter: str = "all",
        subreddit_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Queries and paginates samples across dataset splits."""
        self._ensure_loaded()
        if split in self._dfs:
            target_df = self._dfs[split]
        elif split == "all" and self._dfs:
            target_df = pd.concat(list(self._dfs.values()), ignore_index=True)
        else:
            return {"total": 0, "page": page, "page_size": page_size, "samples": []}

        df = target_df.copy()

        # Keyword text search
        if query_text:
            q_lower = query_text.lower().strip()
            df = df[df["clean_title"].str.lower().str.contains(q_lower, na=False) |
                    df["subreddit"].str.lower().str.contains(q_lower, na=False) |
                    df["id"].astype(str).str.contains(q_lower, na=False)]

        # Veracity filter
        if veracity_filter == "real":
            df = df[df["is_fake"] == 0]
        elif veracity_filter == "fake":
            df = df[df["is_fake"] == 1]
        elif veracity_filter.isdigit():
            lbl_idx = int(veracity_filter)
            if "fakeddit_6_way_label" in df.columns:
                df = df[df["fakeddit_6_way_label"] == lbl_idx]

        # Subreddit filter
        if subreddit_filter and subreddit_filter != "all":
            df = df[df["subreddit"].str.lower() == subreddit_filter.lower()]

        total_matching = len(df)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        sliced_df = df.iloc[start_idx:end_idx]

        samples = []
        for _, row in sliced_df.iterrows():
            img_id = str(row["id"])
            split_name = row.get("split", "test")
            local_img_path = os.path.join(IMAGES_DIR, split_name, f"{img_id}.jpg")
            
            # Check if image exists locally
            has_local_img = os.path.exists(local_img_path)
            img_url = f"/images/{split_name}/{img_id}.jpg" if has_local_img else None

            # Fine-grained 6-way label
            six_way_val = int(row.get("fakeddit_6_way_label", 0)) if pd.notna(row.get("fakeddit_6_way_label")) else None
            six_way_desc = FAKEDDIT_6WAY_LABELS.get(six_way_val, "Unspecified")

            samples.append({
                "id": img_id,
                "clean_title": row["clean_title"],
                "is_fake": int(row["is_fake"]),
                "veracity": "Fake News" if int(row["is_fake"]) == 1 else "Authentic News",
                "six_way_label": six_way_val,
                "six_way_description": six_way_desc,
                "subreddit": str(row.get("subreddit", "news")),
                "score": int(row.get("score", 0)),
                "num_comments": int(row.get("num_comments", 0)),
                "upvote_ratio": float(row.get("upvote_ratio", 0.8)),
                "split": split_name,
                "has_image": has_local_img,
                "image_url": img_url,
                "local_image_path": local_img_path if has_local_img else None
            })

        return {
            "status": "success",
            "total": total_matching,
            "page": page,
            "page_size": page_size,
            "total_pages": int(np.ceil(total_matching / page_size)) if total_matching > 0 else 1,
            "split": split,
            "samples": samples
        }


# Singleton instance
dataset_service = DatasetService()
