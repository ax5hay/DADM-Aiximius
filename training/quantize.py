#!/usr/bin/env python3
"""
Dynamic quantization for ONNX model. Reduces memory and improves CPU inference.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Quantize ONNX model (dynamic int8)")
    p.add_argument("--model", type=Path, required=True, help="FP32 model.onnx")
    p.add_argument("--output", type=Path, default=None, help="Default: model_quantized.onnx")
    p.add_argument("--per_channel", action="store_true", help="Per-channel weight quantization")
    args = p.parse_args()

    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError:
        print("pip install onnxruntime-tools (or onnxruntime with quantization support)")
        return 1

    out = args.output or args.model.parent / (args.model.stem + "_quantized.onnx")
    out.parent.mkdir(parents=True, exist_ok=True)

    quantize_dynamic(
        str(args.model),
        str(out),
        weight_type=QuantType.QInt8,
        per_channel=args.per_channel,
        optimize_model=True,
    )
    print(f"Saved quantized model to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
