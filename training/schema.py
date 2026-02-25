"""
DADM behavioral feature schema. Must stay in sync with edge agent (agent/src/features/behavioral.rs).
Raw sensitive data is not stored long-term on edge; server holds raw data for training.
"""

from __future__ import annotations

import numpy as np
from typing import List, Tuple

FEATURE_SCHEMA_VERSION = "1.0"
CORE_FEATURE_DIM = 12
FEATURE_DIM = 64  # padded for model input

FEATURE_NAMES = [
    "process_count",
    "network_count",
    "file_count",
    "privilege_count",
    "unique_process_names",
    "avg_cmdline_len",
    "total_bytes_sent_norm",
    "total_bytes_recv_norm",
    "unique_file_paths",
    "total_file_size_norm",
    "privilege_success",
    "privilege_fail",
]

NORMALIZATION = {
    "process_count": (1000.0, 0.0),
    "network_count": (1000.0, 0.0),
    "file_count": (1000.0, 0.0),
    "privilege_count": (1000.0, 0.0),
    "unique_process_names": (500.0, 0.0),
    "avg_cmdline_len": (1000.0, 0.0),
    "total_bytes_sent_norm": (1e9, 1.0),   # cap at 1
    "total_bytes_recv_norm": (1e9, 1.0),
    "unique_file_paths": (1000.0, 0.0),
    "total_file_size_norm": (1e9, 1.0),
    "privilege_success": (100.0, 0.0),
    "privilege_fail": (100.0, 0.0),
}


def normalize_core(raw: np.ndarray) -> np.ndarray:
    """Normalize 12 core features to [0,1]-like scale. raw: (N, 12)."""
    out = np.zeros_like(raw, dtype=np.float32)
    for i in range(min(12, raw.shape[1])):
        div, cap = NORMALIZATION[FEATURE_NAMES[i]]
        if cap > 0:
            out[:, i] = np.minimum(raw[:, i] / div, cap).astype(np.float32)
        else:
            out[:, i] = (raw[:, i] / div).astype(np.float32)
    return out


def to_model_input(core: np.ndarray) -> np.ndarray:
    """Pad core (N, 12) to (N, FEATURE_DIM) for model."""
    n = core.shape[0]
    out = np.zeros((n, FEATURE_DIM), dtype=np.float32)
    out[:, :CORE_FEATURE_DIM] = core[:, :CORE_FEATURE_DIM]
    return out


def validate_shape(x: np.ndarray) -> Tuple[bool, str]:
    """Validate batch of feature vectors. Returns (ok, message)."""
    if x.ndim != 2:
        return False, f"expected 2D array, got ndim={x.ndim}"
    if x.shape[1] != FEATURE_DIM:
        return False, f"expected feature_dim={FEATURE_DIM}, got {x.shape[1]}"
    if not np.issubdtype(x.dtype, np.floating):
        return False, f"expected float dtype, got {x.dtype}"
    return True, ""
