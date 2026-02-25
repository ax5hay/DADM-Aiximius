#!/usr/bin/env python3
"""
Explainability: feature importance via reconstruction error (autoencoder) or SHAP approximation.
Server-side or offline; can export top-k indices for edge display.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml
import torch

from schema import FEATURE_DIM, FEATURE_NAMES, CORE_FEATURE_DIM
from models import AnomalyAutoencoder


def reconstruction_importance(model: AnomalyAutoencoder, x: torch.Tensor) -> np.ndarray:
    """Per-feature importance: increase in reconstruction error when feature is zeroed."""
    model.eval()
    with torch.no_grad():
        base_recon = model(x)
        base_err = ((x - base_recon) ** 2).sum(dim=1)
        imp = np.zeros((x.shape[0], x.shape[1]), dtype=np.float32)
        for j in range(x.shape[1]):
            x_masked = x.clone()
            x_masked[:, j] = 0.0
            recon_j = model(x_masked)
            err_j = ((x - recon_j) ** 2).sum(dim=1)
            imp[:, j] = (err_j - base_err).cpu().numpy()  # higher = more important for anomaly
    return imp


def main():
    p = argparse.ArgumentParser(description="Feature importance for anomaly model")
    p.add_argument("--model", type=Path, required=True, help="model.pt")
    p.add_argument("--data", type=Path, required=True, help="Sample (N,D) .npy")
    p.add_argument("--method", choices=["reconstruction", "shap"], default="reconstruction")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()

    with open(Path("config.yaml")) as f:
        config = yaml.safe_load(f)
    model_cfg = config.get("model", {})

    model = AnomalyAutoencoder(
        input_dim=FEATURE_DIM,
        hidden_dims=model_cfg.get("hidden_dims", [32, 16]),
        latent_dim=model_cfg.get("latent_dim", 8),
        dropout=0.0,
    )
    model.load_state_dict(torch.load(args.model, map_location="cpu", weights_only=True))
    model.eval()

    x = np.load(args.data).astype(np.float32)
    if x.shape[1] != FEATURE_DIM:
        from schema import to_model_input, normalize_core
        if x.shape[1] == CORE_FEATURE_DIM:
            x = to_model_input(normalize_core(x))
        else:
            raise ValueError(f"Expected {FEATURE_DIM} or {CORE_FEATURE_DIM} features")
    x_t = torch.from_numpy(x[:64])  # limit for speed

    if args.method == "reconstruction":
        imp = reconstruction_importance(model, x_t)
        # (N, D) -> mean over samples
        mean_imp = imp.mean(axis=0)
    else:
        try:
            import shap
            # KernelExplainer needs callable; wrap model anomaly_score
            def pred(x_batch):
                t = torch.from_numpy(x_batch.astype(np.float32))
                with torch.no_grad():
                    return model.anomaly_score(t).numpy()
            background = x_t[:20].numpy()
            explainer = shap.KernelExplainer(pred, background)
            shap_vals = explainer.shap_values(x_t[:10].numpy(), nsamples=50)
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[0]
            mean_imp = np.abs(shap_vals).mean(axis=0)
        except ImportError:
            print("SHAP requires: pip install shap. Falling back to reconstruction.")
            mean_imp = reconstruction_importance(model, x_t).mean(axis=0)

    top = np.argsort(mean_imp)[::-1][: args.top_k]
    print("Top-k feature importance (anomaly contribution):")
    for i, idx in enumerate(top):
        name = FEATURE_NAMES[idx] if idx < CORE_FEATURE_DIM else f"feature_{idx}"
        print(f"  {i+1}. {name} (idx={idx}) = {mean_imp[idx]:.6f}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        np.savez(args.output, importance=mean_imp, top_k_indices=top, feature_names=FEATURE_NAMES)
        print(f"Saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
