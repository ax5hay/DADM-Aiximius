"""
Gradient compression: top-K sparsification + 16-bit quantization.
Reduces payload size for intermittent links; server reconstructs before aggregation.
"""

from __future__ import annotations

import struct
from typing import List, Tuple

import numpy as np


def compress_gradients(
    grad_list: List[np.ndarray], top_k_ratio: float = 0.15, bits: int = 16
) -> Tuple[bytes, dict]:
    """
    Flatten gradients, keep top-K by magnitude, quantize to `bits` bits.
    Returns (compressed_bytes, meta) where meta has scale and shape for each tensor.
    """
    flat = np.concatenate([g.flatten() for g in grad_list])
    k = max(1, int(len(flat) * top_k_ratio))
    ind = np.argsort(np.abs(flat))[::-1][:k]
    values = flat[ind].astype(np.float32)
    scale = np.abs(values).max()
    if scale < 1e-9:
        scale = 1.0
    values_norm = values / scale
    if bits == 16:
        # map [-1,1] to int16
        quant = (values_norm * 32767).astype(np.int16)
        pack_fmt = "h"
    else:
        quant = (values_norm * 127).astype(np.int8)
        pack_fmt = "b"
    meta = {
        "scale": float(scale),
        "shapes": [tuple(g.shape) for g in grad_list],
        "total_params": sum(g.size for g in grad_list),
        "top_k": k,
        "bits": bits,
    }
    indices_bytes = ind.astype(np.int32).tobytes()
    out = struct.pack("f", scale) + struct.pack("I", k) + quant.tobytes() + indices_bytes
    return out, meta


def decompress_gradients(compressed: bytes, meta: dict) -> List[np.ndarray]:
    """Reconstruct gradient list from compressed bytes and meta (server-side after decrypt)."""
    scale = struct.unpack("f", compressed[:4])[0]
    k = struct.unpack("I", compressed[4:8])[0]
    quant = np.frombuffer(compressed[8 : 8 + k * 2], dtype=np.int16)
    indices = np.frombuffer(compressed[8 + k * 2 : 8 + k * 2 + k * 4], dtype=np.int32)
    total = meta["total_params"]
    flat = np.zeros(total, dtype=np.float32)
    values = quant.astype(np.float32) / 32767.0 * scale
    flat[indices] = values
    shapes = [tuple(s) for s in meta["shapes"]]
    out = []
    offset = 0
    for s in shapes:
        n = int(np.prod(s))
        out.append(flat[offset : offset + n].reshape(s))
        offset += n
    return out


def state_dict_to_grad_list(state_dict: dict) -> List[np.ndarray]:
    """Ordered list of numpy arrays from state_dict (same order for compress/decompress)."""
    return [v.numpy() if hasattr(v, "numpy") else np.array(v) for _, v in sorted(state_dict.items())]


def grad_list_to_state_dict(grad_list: List[np.ndarray], keys: List[str]) -> dict:
    """Build state_dict from list of gradient arrays and parameter keys."""
    return dict(zip(keys, [np.array(g) for g in grad_list]))
