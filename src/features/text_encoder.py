"""
Pretrained Transformer Text Feature Extractor.

Extracts normalized 384-dimensional dense semantic representations from post headlines.
Uses sentence-transformers/all-MiniLM-L6-v2.
"""

import logging
from typing import List, Union
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel

logger = logging.getLogger(__name__)

DEFAULT_TEXT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class TextEncoder:
    """Encodes headline text into dense semantic vector representations."""

    def __init__(self, model_name: str = DEFAULT_TEXT_MODEL, device: str = "cpu", max_length: int = 128):
        self.model_name = model_name
        self.device = torch.device(device if torch.cuda.is_available() and device == "cuda" else "cpu")
        self.max_length = max_length

        logger.info(f"Loading text encoder '{model_name}' on device {self.device}...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
            self.model = AutoModel.from_pretrained(model_name, local_files_only=True)
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        self.embedding_dim = self.model.config.hidden_size  # 384 for MiniLM-L6-v2

    @torch.no_grad()
    def encode_batch(self, texts: List[str], batch_size: int = 64) -> np.ndarray:
        """
        Encodes a list of text strings into an (N, embedding_dim) numpy array.
        Performs mean-pooling over attention mask followed by L2 normalization.
        """
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = [str(t) if t is not None else "" for t in texts[i:i + batch_size]]
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt"
            ).to(self.device)

            outputs = self.model(**inputs)
            token_embeddings = outputs.last_hidden_state  # (B, L, H)
            attention_mask = inputs["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()

            sum_embeddings = torch.sum(token_embeddings * attention_mask, 1)
            sum_mask = torch.clamp(attention_mask.sum(1), min=1e-9)
            mean_pooled = sum_embeddings / sum_mask

            # L2 normalization
            normalized = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
            all_embeddings.append(normalized.cpu().numpy())

        return np.vstack(all_embeddings).astype(np.float32)

    def encode_single(self, text: str) -> np.ndarray:
        """Encodes a single string into a 1D numpy vector."""
        return self.encode_batch([text], batch_size=1)[0]
