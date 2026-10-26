"""
Dataset Download and Verification Module for Fakeddit Benchmark Dataset.

This module provides reproducible, token-free import and verification utilities
for the official Fakeddit multimodal benchmark dataset.
Official Repository: https://github.com/entitize/Fakeddit
Reference: Nakamura et al., "r/Fakeddit: A New Multimodal Benchmark Dataset for Fine-grained Fake News Detection", LREC 2020.
"""

import os
import sys
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Official public Google Drive identifiers provided by the Fakeddit authors
# in the official GitHub repository README (no personal tokens required).
OFFICIAL_FAKEDDIT_SOURCES = {
    "v2_0_folder": "https://drive.google.com/drive/folders/1jU7qgDqU1je9Y0PMKJ_f31yXRo5uWGFm",
    "multimodal_train_tsv": {
        "file_id": "1XsOkD3yhxgWu8URMes0S9LVSwuFJ4pT6",
        "relative_path": "data/raw/multimodal_train.tsv",
        "description": "Multimodal training split (564,000 samples, text + image URLs + fine-grained labels)",
        "expected_min_size_mb": 140.0,
    },
    "multimodal_validate_tsv": {
        "file_id": "1Z99QrwpthioZQY2U6HElmnx8jazf7-Kv",
        "relative_path": "data/raw/multimodal_validate.tsv",
        "description": "Multimodal validation split (59,342 samples)",
        "expected_min_size_mb": 15.0,
    },
    "multimodal_test_public_tsv": {
        "file_id": "1p9EewIKVcFbipVRLZNGYc2JbSC7A0SWv",
        "relative_path": "data/raw/multimodal_test_public.tsv",
        "description": "Multimodal public test split (59,319 samples)",
        "expected_min_size_mb": 15.0,
    },
    "full_image_archive": {
        "file_id": "1cjY6HsHaSZuLVHywIxD5xQqng33J5S2b",
        "description": "Full image archive (~114GB uncompressed, covers entire dataset of 1M+ Reddit posts)",
    }
}


def print_download_instructions():
    """Prints clear, reproducible instructions for acquiring the Fakeddit dataset."""
    guide = f"""
========================================================================================
FAKEDDIT DATASET REPRODUCIBLE ACQUISITION AND IMPORT GUIDE
========================================================================================

Official Source:
  Repository: https://github.com/entitize/Fakeddit
  Paper: "r/Fakeddit: A New Multimodal Benchmark Dataset for Fine-grained Fake News Detection"

1. TEXT AND METADATA TSV FILES:
   The official TSV files are hosted publicly on Google Drive (no personal credentials required):
   - multimodal_train.tsv:       Google Drive ID: {OFFICIAL_FAKEDDIT_SOURCES['multimodal_train_tsv']['file_id']}
   - multimodal_validate.tsv:    Google Drive ID: {OFFICIAL_FAKEDDIT_SOURCES['multimodal_validate_tsv']['file_id']}
   - multimodal_test_public.tsv: Google Drive ID: {OFFICIAL_FAKEDDIT_SOURCES['multimodal_test_public_tsv']['file_id']}

   Automated download without credentials:
     python -m src.data.download_instructions --download-tsvs

2. IMAGE DATA ACQUISITION OPTIONS:
   Option A (Recommended for targeted benchmarks, 5,000–10,000 multimodal samples):
     Use the built-in parallel image fetcher which downloads images directly from
     the public 'image_url' column in the TSVs and validates image integrity via PIL:
     python -m src.data.dataset_builder --samples-target 7000

   Option B (Full Archive, ~114 GB):
     Download the complete image archive from Google Drive:
     URL: https://drive.google.com/file/d/{OFFICIAL_FAKEDDIT_SOURCES['full_image_archive']['file_id']}/view
     Extract the images to data/images/ and run the dataset validator.

3. DATA PROTECTION & PRIVACY NOTICE:
   - No personal tokens, API keys, or private accounts are hard-coded.
   - All URLs and IDs originate from the author-published public distribution.
========================================================================================
"""
    print(guide)
    return guide


def verify_raw_splits(base_dir: str = ".") -> Dict[str, Any]:
    """
    Verifies that the raw TSV splits exist and satisfy minimum file sizes.
    """
    status = {}
    for key in ["multimodal_train_tsv", "multimodal_validate_tsv", "multimodal_test_public_tsv"]:
        info = OFFICIAL_FAKEDDIT_SOURCES[key]
        full_path = os.path.join(base_dir, info["relative_path"])
        exists = os.path.exists(full_path)
        size_mb = (os.path.getsize(full_path) / (1024 * 1024)) if exists else 0.0
        status[key] = {
            "path": full_path,
            "exists": exists,
            "size_mb": round(size_mb, 2),
            "valid": exists and size_mb >= info["expected_min_size_mb"]
        }
    return status


def download_official_tsvs(base_dir: str = "."):
    """
    Downloads any missing official Fakeddit TSVs using gdown without tokens.
    """
    import gdown
    raw_dir = os.path.join(base_dir, "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    for key in ["multimodal_train_tsv", "multimodal_validate_tsv", "multimodal_test_public_tsv"]:
        info = OFFICIAL_FAKEDDIT_SOURCES[key]
        dest = os.path.join(base_dir, info["relative_path"])
        if os.path.exists(dest) and os.path.getsize(dest) / (1024 * 1024) >= info["expected_min_size_mb"]:
            print(f"[{key}] Already present at {dest} ({os.path.getsize(dest) / (1024 * 1024):.2f} MB)")
            continue
        print(f"[{key}] Downloading from Google Drive ID {info['file_id']}...")
        gdown.download(id=info['file_id'], output=dest, quiet=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fakeddit Download and Verification Guide")
    parser.add_argument("--guide", action="store_true", help="Print download guide")
    parser.add_argument("--verify", action="store_true", help="Verify raw dataset files")
    parser.add_argument("--download-tsvs", action="store_true", help="Download missing TSVs")
    args = parser.parse_args()

    if args.download_tsvs:
        download_official_tsvs()
    elif args.verify:
        results = verify_raw_splits()
        print("Raw Split Verification Status:")
        for k, v in results.items():
            print(f"  {k}: Exists={v['exists']}, Size={v['size_mb']}MB, Valid={v['valid']}")
    else:
        print_download_instructions()
