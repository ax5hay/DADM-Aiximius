#!/usr/bin/env python3
"""
Export trained model to ONNX. Fixed input [1, 64] for edge; CPU-only ops.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import yaml

from schema import FEATURE_DIM
from models import AnomalyAutoencoder


def main():
    p = argparse.ArgumentParser(description="Export DADM anomaly model to ONNX")
    p.add_argument("--checkpoint", type=Path, required=True, help="model.pt (state_dict)")
    p.add_argument("--config", type=Path, default=Path("config.yaml"))
    p.add_argument("--output", type=Path, default=Path("model.onnx"))
    p.add_argument("--opset", type=int, default=14)
    p.add_argument("--input-name", default="input")
    p.add_argument("--output-name", default="output")
    args = p.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)
    model_cfg = config.get("model", {})
    onnx_cfg = config.get("onnx", {})

    opset = onnx_cfg.get("opset", args.opset)
    input_name = onnx_cfg.get("input_name", args.input_name)
    output_name = onnx_cfg.get("output_name", args.output_name)

    model = AnomalyAutoencoder(
        input_dim=FEATURE_DIM,
        hidden_dims=model_cfg.get("hidden_dims", [32, 16]),
        latent_dim=model_cfg.get("latent_dim", 8),
        dropout=0.0,
    )
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()

    # Wrapper that outputs anomaly score only
    class ScoreWrapper(torch.nn.Module):
        def __init__(self, ae):
            super().__init__()
            self.ae = ae
        def forward(self, x):
            return self.ae.anomaly_score(x)

    wrapped = ScoreWrapper(model)
    dummy = torch.zeros(1, FEATURE_DIM, dtype=torch.float32)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        wrapped,
        dummy,
        str(args.output),
        input_names=[input_name],
        output_names=[output_name],
        dynamic_axes=None,
        opset_version=opset,
        do_constant_folding=True,
    )
    print(f"Exported {args.output} (opset={opset})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
