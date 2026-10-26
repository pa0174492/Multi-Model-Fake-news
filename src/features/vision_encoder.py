"""
Pretrained Vision Feature Extractor.

Extracts normalized 512-dimensional visual representations using ResNet-18.
"""

import os
import logging
from typing import List, Tuple, Union, Optional
import numpy as np
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image

logger = logging.getLogger(__name__)


class VisionEncoder:
    """Extracts visual representations from images using pretrained ResNet."""

    def __init__(self, device: str = "cpu"):
        self.device = torch.device(device if torch.cuda.is_available() and device == "cuda" else "cpu")
        logger.info(f"Loading pretrained ResNet-18 vision backbone on device {self.device}...")

        weights = models.ResNet18_Weights.DEFAULT
        backbone = models.resnet18(weights=weights)
        # Strip final classification layer to use 512-dim pooled representation
        self.feature_extractor = torch.nn.Sequential(*list(backbone.children())[:-1])
        self.feature_extractor.to(self.device)
        self.feature_extractor.eval()

        self.transform = weights.transforms()
        self.embedding_dim = 512

    def load_and_transform_image(self, image_path: str) -> Tuple[bool, Optional[torch.Tensor]]:
        """Safely loads and preprocesses an image file."""
        if not os.path.exists(image_path):
            return False, None
        try:
            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                tensor = self.transform(img_rgb)
                return True, tensor
        except Exception as e:
            logger.warning(f"Failed to process image {image_path}: {e}")
            return False, None

    @torch.no_grad()
    def encode_batch(self, image_paths: List[str], batch_size: int = 32) -> Tuple[np.ndarray, np.ndarray]:
        """
        Encodes a list of image paths into:
        1) (N, embedding_dim) visual embedding matrix
        2) (N,) binary validity mask (1 = valid image, 0 = fallback zero-vector)
        """
        all_embeddings = []
        valid_masks = []

        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]
            tensors = []
            mask = []

            for path in batch_paths:
                ok, tensor = self.load_and_transform_image(path)
                if ok and tensor is not None:
                    tensors.append(tensor)
                    mask.append(1)
                else:
                    # Dummy tensor for batch shape consistency
                    tensors.append(torch.zeros(3, 224, 224))
                    mask.append(0)

            batch_tensor = torch.stack(tensors).to(self.device)
            features = self.feature_extractor(batch_tensor)  # (B, 512, 1, 1)
            features = torch.flatten(features, 1)            # (B, 512)

            # L2 normalize
            normalized = torch.nn.functional.normalize(features, p=2, dim=1)
            emb_numpy = normalized.cpu().numpy()

            # Zero out embeddings for invalid images
            for idx, valid in enumerate(mask):
                if valid == 0:
                    emb_numpy[idx] = np.zeros(self.embedding_dim, dtype=np.float32)

            all_embeddings.append(emb_numpy)
            valid_masks.extend(mask)

        return np.vstack(all_embeddings).astype(np.float32), np.array(valid_masks, dtype=np.int32)

    def encode_single(self, image_path: str) -> Tuple[np.ndarray, int]:
        """Encodes a single image file."""
        embs, masks = self.encode_batch([image_path], batch_size=1)
        return embs[0], masks[0]
