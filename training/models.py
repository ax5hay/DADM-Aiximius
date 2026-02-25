"""
Model implementations: Autoencoder (primary), Isolation Forest baseline, Tiny Transformer.
All CPU-friendly; &lt;100MB footprint; &lt;10ms inference target.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from typing import List, Optional

from schema import FEATURE_DIM


# ---- Autoencoder (recommended) ----
class AnomalyAutoencoder(nn.Module):
    """Small MLP autoencoder. Reconstruction error = anomaly score proxy."""

    def __init__(
        self,
        input_dim: int = FEATURE_DIM,
        hidden_dims: List[int] = (32, 16),
        latent_dim: int = 8,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        layers = []
        d = input_dim
        for h in hidden_dims:
            layers += [nn.Linear(d, h), nn.ReLU(inplace=True), nn.Dropout(dropout)]
            d = h
        layers.append(nn.Linear(d, latent_dim))
        self.encoder = nn.Sequential(*layers)

        layers_d = []
        d = latent_dim
        for h in reversed(hidden_dims):
            layers_d += [nn.Linear(d, h), nn.ReLU(inplace=True)]
            d = h
        layers_d.append(nn.Linear(d, input_dim))
        self.decoder = nn.Sequential(*layers_d)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        recon = self.decoder(z)
        return recon

    def anomaly_score(self, x: torch.Tensor) -> torch.Tensor:
        """L2 reconstruction error per sample, normalized to [0,1] via sigmoid of scaled error."""
        recon = self.forward(x)
        err = ((x - recon) ** 2).sum(dim=1, keepdim=True)
        # scale so typical values sit in (0,1); then sigmoid
        scale = 1.0 / (1.0 + err.mean().item()) if err.numel() > 0 else 1.0
        return torch.sigmoid(err * scale).clamp(0.0, 1.0)


# ---- Tiny Transformer (optional) ----
class TinyTransformer(nn.Module):
    """Minimal transformer for sequence of feature vectors. Single-vector input = seq_len 1."""

    def __init__(
        self,
        input_dim: int = FEATURE_DIM,
        d_model: int = 32,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 64,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            norm_first=False,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Linear(d_model // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, D) -> (B, 1, D)
        if x.dim() == 2:
            x = x.unsqueeze(1)
        x = self.input_proj(x)
        x = self.transformer(x)
        x = x[:, -1]
        return self.head(x)


# ---- Isolation Forest (sklearn baseline) ----
def fit_isolation_forest(x: np.ndarray, contamination: float = 0.01) -> IsolationForest:
    """Fit sklearn Isolation Forest. Anomaly score from decision_function (negative = more anomalous)."""
    clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100, max_samples=256)
    clf.fit(x)
    return clf


def isolation_forest_scores(clf: IsolationForest, x: np.ndarray) -> np.ndarray:
    """Map decision_function to [0,1]. Higher = more anomalous."""
    d = clf.decision_function(x)
    d = np.clip(d, -0.5, 0.5)
    return (0.5 - np.asarray(d, dtype=np.float32)).reshape(-1, 1)
