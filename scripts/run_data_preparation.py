"""
Data Preparation Execution Script.

Builds reproducible multimodal dataset from raw Fakeddit TSVs,
downloads and validates images in parallel, records exclusions,
prevents cross-split leakage, and generates data profiling report.
"""

import os
import sys

# Ensure repository root is in python path
sys.path.insert(0, os.path.abspath("."))

import logging
from src.data.dataset_builder import MultimodalDatasetBuilder
from src.data.download_instructions import verify_raw_splits

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("=== STEP 1: Verifying Raw Official Fakeddit Splits ===")
    status = verify_raw_splits()
    all_ok = True
    for k, v in status.items():
        logger.info(f"  {k}: Exists={v['exists']}, Size={v['size_mb']}MB, Valid={v['valid']}")
        if not v["valid"]:
            all_ok = False

    if not all_ok:
        logger.error("Raw official Fakeddit TSVs are missing or incomplete.")
        sys.exit(1)

    logger.info("=== STEP 2: Building Multimodal Dataset with Complete Modalities ===")
    # Target: 5,000 train, 1,000 val, 1,000 test (total 7,000 complete text-image samples)
    builder = MultimodalDatasetBuilder(
        raw_train_path="data/raw/multimodal_train.tsv",
        raw_val_path="data/raw/multimodal_validate.tsv",
        raw_test_path="data/raw/multimodal_test_public.tsv",
        output_dir="data/processed",
        images_dir="data/images",
        max_workers=24
    )

    datasets = builder.build_all(
        train_target=5000,
        val_target=1000,
        test_target=1000
    )

    logger.info("Data preparation completed successfully!")
    logger.info(f"Train samples: {len(datasets['train'])}")
    logger.info(f"Validation samples: {len(datasets['val'])}")
    logger.info(f"Test samples: {len(datasets['test'])}")


if __name__ == "__main__":
    main()
