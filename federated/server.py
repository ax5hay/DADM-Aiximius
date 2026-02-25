#!/usr/bin/env python3
"""
Federated server (Aiximius): config, accept encrypted updates (decrypt only here), aggregate, version, sign.
Supports async updates, intermittent connectivity, rollback via signed package.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
from flask import Flask, jsonify, request, send_file

# Add parent/training for model
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
from models import AnomalyAutoencoder  # noqa: E402
from schema import FEATURE_DIM  # noqa: E402


class ScoreWrapper(torch.nn.Module):
    """Wrapper that outputs anomaly_score(x) so ONNX matches agent expectation [1, 1]."""

    def __init__(self, ae: AnomalyAutoencoder):
        super().__init__()
        self.ae = ae

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.ae.anomaly_score(x)

from compression import decompress_gradients
from crypto_utils import (
    decrypt_at_server,
    generate_keypair,
    sign_model_package,
    verify_model_package,
    verify_signature,
)
from protocol import ConfigResponse, UpdateRequest
from versioning import ModelMetadata, next_version, save_package, load_package

app = Flask(__name__)

# Server state (in production: DB + HSM for signing)
SERVER_STATE = {
    "server_priv": None,
    "server_pub": None,
    "signing_priv": None,
    "signing_pub": None,
    "current_round": 0,
    "model_version": 0,
    "min_clients": 2,
    "grace_seconds": 300,
    "updates": {},  # round -> list of (client_id, grad_list)
    "client_pubkeys": {},  # client_id -> pem
    "registry_dir": Path("registry"),
    "model_shape": None,  # list of param shapes for aggregation
}


def init_server_keys():
    if SERVER_STATE["server_priv"] is None:
        reg = Path("server_keys")
        reg.mkdir(parents=True, exist_ok=True)
        priv_p = reg / "server_priv.pem"
        pub_p = reg / "server_pub.pem"
        sign_priv_p = reg / "signing_priv.pem"
        sign_pub_p = reg / "signing_pub.pem"
        if not priv_p.exists():
            priv, pub = generate_keypair()
            priv_p.write_bytes(priv)
            pub_p.write_bytes(pub)
            sign_priv, sign_pub = generate_keypair()
            sign_priv_p.write_bytes(sign_priv)
            sign_pub_p.write_bytes(sign_pub)
        SERVER_STATE["server_priv"] = priv_p.read_bytes()
        SERVER_STATE["server_pub"] = pub_p.read_bytes()
        SERVER_STATE["signing_priv"] = sign_priv_p.read_bytes()
        SERVER_STATE["signing_pub"] = sign_pub_p.read_bytes()
    SERVER_STATE["registry_dir"].mkdir(parents=True, exist_ok=True)


def get_param_shapes():
    if SERVER_STATE["model_shape"] is None:
        m = AnomalyAutoencoder(input_dim=FEATURE_DIM, hidden_dims=[32, 16], latent_dim=8, dropout=0.0)
        SERVER_STATE["model_shape"] = [tuple(p.shape) for _, p in sorted(m.state_dict().items())]
    return SERVER_STATE["model_shape"]


@app.route("/config", methods=["GET"])
def get_config():
    init_server_keys()
    return jsonify(ConfigResponse(
        current_round=SERVER_STATE["current_round"],
        model_version=SERVER_STATE["model_version"],
        server_public_key=SERVER_STATE["server_pub"].decode(),
        min_clients=SERVER_STATE["min_clients"],
        grace_seconds=SERVER_STATE["grace_seconds"],
        schema_version="1.0",
    ).to_dict())


@app.route("/updates", methods=["POST"])
def post_update():
    init_server_keys()
    body = request.get_json()
    if not body:
        return jsonify({"error": "missing body"}), 400
    try:
        req = UpdateRequest.from_dict(body)
    except (KeyError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

    # Idempotency: same client_id + round only once
    key = (req.client_id, req.round)
    if req.round not in SERVER_STATE["updates"]:
        SERVER_STATE["updates"][req.round] = []
    if any(cid == req.client_id for cid, _ in SERVER_STATE["updates"][req.round]):
        return jsonify({"status": "accepted", "message": "duplicate ignored"}), 202

    # Verify signature (client must be registered or we accept any for demo)
    payload_for_sig = json.dumps({
        "client_id": req.client_id,
        "round": req.round,
        "encrypted_payload": req.encrypted_payload,
        "schema_version": req.schema_version,
    }, sort_keys=True).encode()
    sig = base64.b64decode(req.signature)
    client_pub = SERVER_STATE["client_pubkeys"].get(req.client_id)
    if client_pub and not verify_signature(payload_for_sig, sig, client_pub):
        return jsonify({"error": "invalid signature"}), 401
    # If no client_pub, skip verify (demo mode)

    # Decrypt only at server (Aiximius)
    try:
        encrypted = base64.b64decode(req.encrypted_payload)
        plaintext = decrypt_at_server(encrypted, SERVER_STATE["server_priv"])
    except Exception as e:
        return jsonify({"error": "decrypt failed"}), 400

    # Decompress
    meta = req.compression_meta
    meta["shapes"] = [tuple(s) for s in meta.get("shapes", [])]
    try:
        grad_list = decompress_gradients(plaintext, meta)
    except Exception as e:
        return jsonify({"error": f"decompress failed: {e}"}), 400

    SERVER_STATE["updates"][req.round].append((req.client_id, grad_list))
    return jsonify({"status": "accepted"}), 202


def aggregate_fedavg(grad_lists: List[List[np.ndarray]]) -> List[np.ndarray]:
    """FedAvg: element-wise mean of gradients."""
    n = len(grad_lists)
    out = []
    for i in range(len(grad_lists[0])):
        stacked = np.stack([g[i] for g in grad_lists])
        out.append(stacked.mean(axis=0).astype(np.float32))
    return out


def run_aggregation_and_publish():
    """When cohort is ready: FedAvg gradients, apply to global model, sign, save."""
    init_server_keys()
    r = SERVER_STATE["current_round"]
    if r not in SERVER_STATE["updates"] or len(SERVER_STATE["updates"][r]) < SERVER_STATE["min_clients"]:
        return None
    grad_lists = [gl for _, gl in SERVER_STATE["updates"][r]]
    avg_grad = aggregate_fedavg(grad_lists)
    model = AnomalyAutoencoder(input_dim=FEATURE_DIM, hidden_dims=[32, 16], latent_dim=8, dropout=0.0)
    if "global_state" in SERVER_STATE and SERVER_STATE["global_state"]:
        model.load_state_dict(SERVER_STATE["global_state"])
    lr = 0.1
    state = model.state_dict()
    keys = sorted(state.keys())
    for i, k in enumerate(keys):
        if i < len(avg_grad):
            state[k] = state[k] - lr * torch.from_numpy(avg_grad[i])
    model.load_state_dict(state)
    SERVER_STATE["global_state"] = {k: v.clone() for k, v in model.state_dict().items()}
    # Export to ONNX bytes (anomaly_score output [1,1] for agent)
    import io
    wrapped = ScoreWrapper(model)
    dummy = torch.zeros(1, FEATURE_DIM)
    buf = io.BytesIO()
    torch.onnx.export(
        wrapped, dummy, buf,
        input_names=["input"], output_names=["output"],
        dynamic_axes=None, opset_version=14,
    )
    model_blob = buf.getvalue()
    new_version = next_version(SERVER_STATE["model_version"])
    metadata = ModelMetadata(
        version=new_version,
        base_round=r,
        created_at=__import__("time").time(),
        schema_version="1.0",
        rollback_of=None,
    )
    sig = sign_model_package(model_blob, metadata.to_bytes(), SERVER_STATE["signing_priv"])
    save_package(SERVER_STATE["registry_dir"], new_version, model_blob, metadata, sig)
    SERVER_STATE["model_version"] = new_version
    SERVER_STATE["current_round"] = r + 1
    return new_version


def bootstrap_version_zero():
    """Create initial signed model v0 so clients can pull (anomaly_score output for agent)."""
    reg = SERVER_STATE["registry_dir"]
    v0_model = reg / "model_v0.onnx"
    if v0_model.exists():
        return
    import time
    import io
    model = AnomalyAutoencoder(input_dim=FEATURE_DIM, hidden_dims=[32, 16], latent_dim=8, dropout=0.0)
    wrapped = ScoreWrapper(model)
    buf = io.BytesIO()
    torch.onnx.export(
        wrapped, torch.zeros(1, FEATURE_DIM), buf,
        input_names=["input"], output_names=["output"],
        dynamic_axes=None, opset_version=14,
    )
    model_blob = buf.getvalue()
    metadata = ModelMetadata(version=0, base_round=0, created_at=time.time(), schema_version="1.0", rollback_of=None)
    sig = sign_model_package(model_blob, metadata.to_bytes(), SERVER_STATE["signing_priv"])
    save_package(reg, 0, model_blob, metadata, sig)
    SERVER_STATE["model_version"] = 0


@app.route("/model")
def get_model():
    init_server_keys()
    bootstrap_version_zero()
    version = request.args.get("version", type=int)
    if version is None:
        version = SERVER_STATE["model_version"]
    try:
        model_blob, metadata, sig = load_package(SERVER_STATE["registry_dir"], version)
    except FileNotFoundError:
        return jsonify({"error": "version not found"}), 404
    from dataclasses import asdict
    return jsonify({
        "version": metadata.version,
        "model_blob_b64": base64.b64encode(model_blob).decode(),
        "metadata": asdict(metadata),
        "signature_b64": base64.b64encode(sig).decode(),
    })


@app.route("/model/verify", methods=["POST"])
def verify_and_save_model():
    """Verify signed package (e.g. after air-gap transfer)."""
    init_server_keys()
    body = request.get_json()
    if not body:
        return jsonify({"error": "missing body"}), 400
    model_b64 = body.get("model_blob_b64")
    meta = body.get("metadata")
    sig_b64 = body.get("signature_b64")
    if not all([model_b64, meta, sig_b64]):
        return jsonify({"error": "missing fields"}), 400
    model_blob = base64.b64decode(model_b64)
    metadata_bytes = json.dumps(meta, sort_keys=True).encode() if isinstance(meta, dict) else base64.b64decode(meta)
    sig = base64.b64decode(sig_b64)
    ok = verify_model_package(model_blob, metadata_bytes, sig, SERVER_STATE["signing_pub"])
    return jsonify({"verified": ok})


@app.route("/aggregate", methods=["POST"])
def trigger_aggregate():
    """Trigger aggregation for current round (demo)."""
    v = run_aggregation_and_publish()
    if v is None:
        return jsonify({"status": "cohort not ready"}), 200
    return jsonify({"status": "published", "version": v}), 200


@app.route("/rollback", methods=["POST"])
def rollback():
    """Mark current version as bad; next /model will serve previous. In production: publish signed rollback package."""
    body = request.get_json() or {}
    to_version = body.get("to_version", max(0, SERVER_STATE["model_version"] - 1))
    SERVER_STATE["model_version"] = to_version
    return jsonify({"status": "rollback", "active_version": to_version}), 200


def main():
    import argparse
    p = argparse.ArgumentParser(description="Federated server (decrypt only here)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args()
    init_server_keys()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
