#!/usr/bin/env python3
"""
Drift detection: compare current feature distribution to reference (training or baseline).
Server-side: run on aggregated stats; no raw edge data needed long-term.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.stats import wasserstein_distance


def psi(baseline: np.ndarray, current: np.ndarray, n_bins: int = 10) -> float:
    """Population Stability Index between two 1D distributions."""
    min_val = min(baseline.min(), current.min())
    max_val = max(baseline.max(), current.max())
    if max_val <= min_val:
        max_val = min_val + 1.0
    bins = np.linspace(min_val, max_val, n_bins + 1)
    p = np.histogram(baseline, bins=bins)[0].astype(np.float64)
    q = np.histogram(current, bins=bins)[0].astype(np.float64)
    p = p / (p.sum() + 1e-12)
    q = q / (q.sum() + 1e-12)
    p = np.clip(p, 1e-6, 1.0)
    q = np.clip(q, 1e-6, 1.0)
    return np.sum((q - p) * np.log(q / p))


def main():
    p = argparse.ArgumentParser(description="Drift detection vs reference")
    p.add_argument("--reference", type=Path, required=True, help="drift_reference.npz or (N,D) .npy")
    p.add_argument("--current", type=Path, required=True, help="Current batch (M,D) .npy")
    p.add_argument("--psi-threshold", type=float, default=0.25)
    p.add_argument("--wasserstein-threshold", type=float, default=0.15)
    p.add_argument("--per-feature", action="store_true", help="Report per-feature drift")
    args = p.parse_args()

    np.random.seed(42)
    if args.reference.suffix == ".npz":
        ref = np.load(args.reference)
        mean = ref["mean"]
        std = ref["std"]
        n_ref = int(ref["n"])
        baseline_synth = np.random.randn(n_ref, len(mean)).astype(np.float32) * std + mean
    else:
        baseline_synth = np.load(args.reference).astype(np.float32)
        mean = baseline_synth.mean(axis=0)
        std = baseline_synth.std(axis=0) + 1e-8

    current = np.load(args.current).astype(np.float32)
    if current.shape[1] != baseline_synth.shape[1]:
        print("Feature dim mismatch")
        return 1

    n_features = current.shape[1]
    psi_vals = []
    wass_vals = []
    for i in range(n_features):
        psi_vals.append(psi(baseline_synth[:, i], current[:, i]))
        wass_vals.append(wasserstein_distance(baseline_synth[:, i], current[:, i]))

    psi_mean = float(np.mean(psi_vals))
    wass_mean = float(np.mean(wass_vals))
    print(f"PSI (mean over features): {psi_mean:.4f} (threshold={args.psi_threshold})")
    print(f"Wasserstein (mean):       {wass_mean:.4f} (threshold={args.wasserstein_threshold})")
    drifted = psi_mean > args.psi_threshold or wass_mean > args.wasserstein_threshold
    print(f"Drift detected: {drifted}")

    if args.per_feature:
        print("\nPer-feature PSI / Wasserstein:")
        for i in range(min(12, n_features)):
            print(f"  {i}: PSI={psi_vals[i]:.4f}  W={wass_vals[i]:.4f}")
    return 0 if not drifted else 2


if __name__ == "__main__":
    raise SystemExit(main())
