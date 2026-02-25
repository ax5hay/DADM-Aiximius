#!/usr/bin/env python3
"""
Federated client: local training on feature data only (no raw logs), compress, encrypt, sign, push.
Tolerates intermittent connectivity with retries and optional local queue.
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

# Add parent/training for model and schema
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
from schema import FEATURE_DIM, to_model_input, normalize_core, CORE_FEATURE_DIM  # noqa: E402
from models import AnomalyAutoencoder  # noqa: E402

from compression import compress_gradients, state_dict_to_grad_list
from crypto_utils import encrypt_for_server, sign_payload


def get_gradients(model: torch.nn.Module, x: torch.Tensor) -> list[np.ndarray]:
    """Compute gradients w.r.t. model parameters on local batch (no raw logs; x is feature vectors only)."""
    model.train()
    model.zero_grad()
    recon = model(x)
    loss = ((x - recon) ** 2).mean()
    loss.backward()
    grad_list = []
    for p in model.parameters():
        if p.grad is not None:
            grad_list.append(p.grad.detach().cpu().numpy().copy())
        else:
            grad_list.append(np.zeros_like(p.detach().cpu().numpy()))
    return grad_list


def run_client_round(
    base_url: str,
    client_id: str,
    client_private_key_pem: bytes,
    server_public_key_pem: bytes,
    model: torch.nn.Module,
    feature_batch: np.ndarray,
    round_id: int,
    schema_version: str = "1.0",
    top_k_ratio: float = 0.15,
) -> bool:
    """
    One round: compute gradients on feature_batch (no raw logs), compress, encrypt, sign, POST.
    Returns True if accepted.
    """
    import requests

    x = torch.from_numpy(feature_batch.astype(np.float32))
    grad_list = get_gradients(model, x)
    compressed, meta = compress_gradients(grad_list, top_k_ratio=top_k_ratio)
    encrypted = encrypt_for_server(compressed, server_public_key_pem)
    enc_b64 = base64.b64encode(encrypted).decode()
    payload_for_sig = json.dumps({
        "client_id": client_id,
        "round": round_id,
        "encrypted_payload": enc_b64,
        "schema_version": schema_version,
    }, sort_keys=True).encode()
    signature = sign_payload(payload_for_sig, client_private_key_pem)

    # Meta must be JSON-serializable (tuples -> list)
    meta_ser = {k: (list(v) if isinstance(v, (list, tuple)) and v and isinstance(v[0], (list, tuple)) else v)
                for k, v in meta.items()}
    if "shapes" in meta_ser:
        meta_ser["shapes"] = [list(s) for s in meta["shapes"]]

    req = {
        "client_id": client_id,
        "round": round_id,
        "encrypted_payload": enc_b64,
        "compression_meta": meta_ser,
        "signature": base64.b64encode(signature).decode(),
        "schema_version": schema_version,
    }

    for attempt in range(3):
        try:
            r = requests.post(
                f"{base_url.rstrip('/')}/updates",
                json=req,
                timeout=30,
            )
            if r.status_code in (200, 202):
                return True
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            return False
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return False


def main():
    import argparse
    from crypto_utils import generate_keypair

    p = argparse.ArgumentParser(description="Federated client (no raw logs; encrypted updates)")
    p.add_argument("--server", default="http://127.0.0.1:5000", help="Server base URL")
    p.add_argument("--client-id", default="client-1")
    p.add_argument("--data", type=Path, default=None, help="Feature .npy (N, 12 or N, 64)")
    p.add_argument("--round", type=int, default=None, help="Round (default: from server config)")
    p.add_argument("--keys-dir", type=Path, default=Path("client_keys"), help="Dir for client keypair")
    args = p.parse_args()

    args.keys_dir.mkdir(parents=True, exist_ok=True)
    priv_path = args.keys_dir / "client_priv.pem"
    pub_path = args.keys_dir / "client_pub.pem"
    if not priv_path.exists():
        priv, pub = generate_keypair()
        priv_path.write_bytes(priv)
        pub_path.write_bytes(pub)
        print(f"Generated keypair in {args.keys_dir}")
    client_priv = priv_path.read_bytes()
    client_pub = pub_path.read_bytes()

    import requests
    r = requests.get(f"{args.server.rstrip('/')}/config", timeout=10)
    r.raise_for_status()
    config = r.json()
    server_pub = config["server_public_key"].encode() if isinstance(config["server_public_key"], str) else config["server_public_key"]
    round_id = args.round if args.round is not None else config["current_round"]

    if args.data and args.data.exists():
        x = np.load(args.data).astype(np.float32)
        if x.shape[1] == CORE_FEATURE_DIM:
            x = to_model_input(normalize_core(x))
    else:
        np.random.seed(42)
        x = np.random.randn(64, FEATURE_DIM).astype(np.float32) * 0.1

    model = AnomalyAutoencoder(input_dim=FEATURE_DIM, hidden_dims=[32, 16], latent_dim=8, dropout=0.0)
    # In production, load current model from server or local cache
    model.eval()

    ok = run_client_round(
        args.server,
        args.client_id,
        client_priv,
        server_pub,
        model,
        x,
        round_id,
        schema_version=config.get("schema_version", "1.0"),
    )
    print("Update accepted" if ok else "Update failed or rejected")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
