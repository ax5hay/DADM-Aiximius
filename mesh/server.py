#!/usr/bin/env python3
"""
Minimal mesh enrollment server: POST /v1/enroll (token + CSR -> cert + config), GET /v1/crl.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from flask import Flask, jsonify, request

from ca_utils import ensure_ca, sign_csr

app = Flask(__name__)

MESH_DATA = Path(os.environ.get("MESH_DATA_DIR", "mesh_data"))
ENROLL_TOKEN = os.environ.get("MESH_ENROLL_TOKEN", "change-me-in-production")


@app.route("/v1/enroll", methods=["POST"])
def enroll():
    """Accept token + CSR; return certificate, CA cert, and config."""
    body = request.get_json() or {}
    token = body.get("token")
    csr_b64 = body.get("csr")
    if not token or not csr_b64:
        return jsonify({"error": "missing token or csr"}), 400
    if token != ENROLL_TOKEN:
        return jsonify({"error": "invalid token"}), 403

    if isinstance(csr_b64, str):
        if "-----" in csr_b64:
            csr_raw = csr_b64.encode()
        else:
            try:
                csr_raw = base64.b64decode(csr_b64)
            except Exception:
                csr_raw = csr_b64.encode()
    else:
        csr_raw = csr_b64

    try:
        ca_key_path = MESH_DATA / "ca_key.pem"
        ca_cert_path = MESH_DATA / "ca_cert.pem"
        ca_priv_pem, ca_cert_pem = ensure_ca(ca_key_path, ca_cert_path)
        cert_pem = sign_csr(csr_raw, ca_priv_pem, ca_cert_pem)
    except Exception as e:
        return jsonify({"error": "invalid CSR or signing failed", "detail": str(e)}), 400

    crl_url = request.url_root.rstrip("/") + "/v1/crl"
    config = {
        "bootstrap_peers": [],
        "gossip_fanout": 3,
        "crl_url": crl_url,
    }

    return jsonify({
        "certificate": cert_pem.decode() if isinstance(cert_pem, bytes) else cert_pem,
        "ca_cert": ca_cert_pem.decode() if isinstance(ca_cert_pem, bytes) else ca_cert_pem,
        "config": config,
    }), 201


@app.route("/v1/crl", methods=["GET"])
def get_crl():
    """Return empty CRL (signed). For minimal server we return a placeholder JSON; full CRL would be DER."""
    return jsonify({"revoked_serials": [], "next_update": None}), 200


@app.route("/v1/health")
def health():
    return jsonify({"status": "ok"}), 200


def main():
    MESH_DATA.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("PORT", 5003))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
