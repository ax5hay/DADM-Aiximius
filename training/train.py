#!/usr/bin/env python3
"""
DADM edge anomaly model — training pipeline.
Data is server-side; no raw sensitive data on edge. Supports federated aggregation (FedAvg) via
saving/loading state dicts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml

from schema import FEATURE_DIM, CORE_FEATURE_DIM, normalize_core, to_model_input, validate_shape
from models import AnomalyAutoencoder, fit_isolation_forest, isolation_forest_scores


def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_data(path: Path) -> np.ndarray:
    """Load server-side feature data: (N, CORE_FEATURE_DIM) or (N, FEATURE_DIM)."""
    ext = path.suffix.lower()
    if ext == ".npy":
        x = np.load(path).astype(np.float32)
    elif ext == ".csv":
        import pandas as pd
        df = pd.read_csv(path)
        x = df.values.astype(np.float32)
    else:
        raise ValueError(f"Unsupported format: {ext}")
    if x.shape[1] == CORE_FEATURE_DIM:
        x = normalize_core(x)
        x = to_model_input(x)
    ok, msg = validate_shape(x)
    if not ok:
        raise ValueError(msg)
    return x


def train_autoencoder(
    x: np.ndarray,
    config: dict,
    device: torch.device,
) -> nn.Module:
    model_cfg = config.get("model", {})
    train_cfg = config.get("training", {})
    hidden = model_cfg.get("hidden_dims", [32, 16])
    latent = model_cfg.get("latent_dim", 8)
    dropout = model_cfg.get("dropout", 0.1)
    epochs = train_cfg.get("epochs", 50)
    batch_size = train_cfg.get("batch_size", 256)
    lr = train_cfg.get("lr", 1.0e-3)
    seed = train_cfg.get("seed", 42)

    torch.manual_seed(seed)
    np.random.seed(seed)

    model = AnomalyAutoencoder(
        input_dim=FEATURE_DIM,
        hidden_dims=hidden,
        latent_dim=latent,
        dropout=dropout,
    ).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    n = len(x)
    val_split = train_cfg.get("val_split", 0.15)
    nval = int(n * val_split)
    perm = np.random.permutation(n)
    train_idx, val_idx = perm[nval:], perm[:nval]
    x_train = torch.from_numpy(x[train_idx])
    x_val = torch.from_numpy(x[val_idx])

    for ep in range(epochs):
        model.train()
        for start in range(0, len(x_train), batch_size):
            batch = x_train[start : start + batch_size].to(device)
            opt.zero_grad()
            recon = model(batch)
            loss = criterion(recon, batch)
            loss.backward()
            opt.step()
        if (ep + 1) % 10 == 0 or ep == 0:
            model.eval()
            with torch.no_grad():
                v_recon = model(x_val.to(device))
                v_loss = criterion(v_recon, x_val.to(device)).item()
            print(f"epoch {ep+1} val_loss={v_loss:.6f}")
    return model


def train_isolation_forest(x: np.ndarray, config: dict):
    contamination = config.get("training", {}).get("contamination", 0.01)
    return fit_isolation_forest(x, contamination=contamination)


def main():
    p = argparse.ArgumentParser(description="Train DADM edge anomaly model (server-side data)")
    p.add_argument("--config", type=Path, default=Path("config.yaml"), help="Config YAML")
    p.add_argument("--data", type=Path, required=True, help="Feature data .npy or .csv (server-side)")
    p.add_argument("--out-dir", type=Path, default=Path("out"), help="Output directory")
    p.add_argument("--model-type", choices=["autoencoder", "isolation_forest"], default=None)
    args = p.parse_args()

    config = load_config(args.config)
    model_type = args.model_type or config.get("model", {}).get("type", "autoencoder")

    x = load_data(args.data)
    print(f"Loaded {x.shape[0]} samples, dim={x.shape[1]}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cpu")

    if model_type == "autoencoder":
        model = train_autoencoder(x, config, device)
        torch.save(model.state_dict(), args.out_dir / "model.pt")
        # Save config and schema version for export
        with open(args.out_dir / "train_config.json", "w") as f:
            json.dump({"model_type": model_type, "feature_dim": FEATURE_DIM}, f, indent=2)
        print(f"Saved model.pt and train_config.json to {args.out_dir}")
    else:
        clf = train_isolation_forest(x, config)
        import joblib
        joblib.dump(clf, args.out_dir / "isolation_forest.joblib")
        with open(args.out_dir / "train_config.json", "w") as f:
            json.dump({"model_type": model_type, "feature_dim": FEATURE_DIM}, f, indent=2)
        print(f"Saved isolation_forest.joblib to {args.out_dir}")

    # Save reference for drift (mean/std or sample)
    np.savez(
        args.out_dir / "drift_reference.npz",
        mean=x.mean(axis=0),
        std=x.std(axis=0) + 1e-8,
        n=x.shape[0],
    )
    print("Saved drift_reference.npz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
