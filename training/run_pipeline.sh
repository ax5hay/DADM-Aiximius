#!/usr/bin/env bash
# Full pipeline: dummy data → train → export ONNX → quantize. Replace data.npy with real server-side data.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Generating dummy feature data (replace with server-side export) ==="
python -c "
import numpy as np
from schema import FEATURE_DIM, CORE_FEATURE_DIM, normalize_core, to_model_input
np.random.seed(42)
x = np.random.rand(5000, CORE_FEATURE_DIM).astype(np.float32) * 100
x = to_model_input(normalize_core(x))
np.save('data.npy', x)
print('Saved data.npy:', x.shape)
"

echo "=== Training ==="
python train.py --data data.npy --out-dir out

echo "=== Export ONNX ==="
python export_onnx.py --checkpoint out/model.pt --output out/model.onnx

echo "=== Quantize (optional) ==="
python quantize.py --model out/model.onnx --output out/model_quantized.onnx

echo "=== Drift check (reference vs current sample) ==="
python drift.py --reference out/drift_reference.npz --current data.npy --per-feature || true

echo "=== Explainability (top-k features) ==="
python explain.py --model out/model.pt --data data.npy --method reconstruction --top-k 5 --output out/importance.npz

echo "=== Done. Model: out/model.onnx (and out/model_quantized.onnx) ==="
