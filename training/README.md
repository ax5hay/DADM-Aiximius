# DADM Edge Anomaly Model — Training

Production-ready Python training pipeline for the edge-optimized anomaly detection model. **CPU-only**, &lt;100MB footprint, &lt;10ms inference; **raw sensitive data server-side only**; federated training supported.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
# Generate dummy data (replace with server-side feature export)
python -c "
import numpy as np
from schema import FEATURE_DIM, CORE_FEATURE_DIM, normalize_core, to_model_input
x = np.random.rand(5000, CORE_FEATURE_DIM).astype(np.float32) * 100
x = to_model_input(normalize_core(x))
np.save('data.npy', x)
"
python train.py --data data.npy --out-dir out
python export_onnx.py --checkpoint out/model.pt --output out/model.onnx
python quantize.py --model out/model.onnx --output out/model_quantized.onnx
```

## Feature schema

See `schema.py` and [EDGE-MODEL-DESIGN.md](../docs/EDGE-MODEL-DESIGN.md). 12 core behavioral features (process, network, file, privilege); vector padded to 64 for model input. Schema must match the edge agent.

## Model choice

| Model | Use case | Federated | ONNX |
|-------|----------|-----------|------|
| **Autoencoder** | Primary; best balance | Yes (FedAvg) | Yes |
| **Isolation Forest** | Baseline; no training | N/A | Via sklearn-onnx |
| **Tiny Transformer** | Sequence-aware (future) | Yes | Yes |

**Secure federated learning:** Encrypted gradient updates, no raw logs, decryption only at server. See [FEDERATED-LEARNING.md](../docs/FEDERATED-LEARNING.md) and sample implementation in `federated/`.

## Scripts

| Script | Purpose |
|--------|--------|
| `train.py` | Train on server-side feature data; saves model.pt, drift_reference.npz |
| `export_onnx.py` | Export PyTorch → ONNX (fixed [1,64] input, score output) |
| `quantize.py` | Dynamic int8 quantization for smaller/faster CPU inference |
| `drift.py` | PSI / Wasserstein vs reference; use for retrain triggers |
| `explain.py` | Feature importance (reconstruction or SHAP); export top-k for high-risk events |

## Config

`config.yaml`: model type, hidden dims, training hyperparams, ONNX opts, quantization, drift thresholds, explainability method.

## Drift and explainability

- **Drift:** Run `drift.py --reference out/drift_reference.npz --current new_batch.npy`. If above threshold, trigger retrain or canary.
- **Explainability:** `explain.py --model out/model.pt --data sample.npy --method reconstruction --top-k 5`. Use for high-risk event inspection; optional SHAP with `pip install shap`.
