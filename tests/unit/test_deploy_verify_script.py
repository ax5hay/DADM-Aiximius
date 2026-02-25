"""Unit test for deploy verify_model_package script."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Build path to script (repo root deploy/ansible/scripts/)
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "ansible" / "scripts" / "verify_model_package.py"


def test_verify_script_missing_args() -> None:
    """Script exits 2 when args missing."""
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True)
    assert r.returncode == 2


def test_verify_script_invalid_signature() -> None:
    """Script exits 1 when signature is invalid."""
    with tempfile.TemporaryDirectory() as d:
        pkg_dir = Path(d)
        # Dummy package.json with bad signature
        pkg_dir.joinpath("package.json").write_text(
            json.dumps({
                "model_blob_b64": base64.b64encode(b"x").decode(),
                "metadata": {"version": 1, "base_round": 0, "created_at": 1.0, "schema_version": "1.0", "rollback_of": None},
                "signature_b64": base64.b64encode(b"bad").decode(),
            })
        )
        # Need a valid PEM pubkey file
        sys.path.insert(0, str(REPO_ROOT / "federated"))
        from crypto_utils import generate_keypair
        _, pub_pem = generate_keypair()
        pubkey_path = pkg_dir / "pub.pem"
        pubkey_path.write_bytes(pub_pem)
        r = subprocess.run([sys.executable, str(SCRIPT), str(pkg_dir), str(pubkey_path)], capture_output=True)
    assert r.returncode == 1


def test_verify_script_valid_signature() -> None:
    """Script exits 0 when signature is valid."""
    sys.path.insert(0, str(REPO_ROOT / "federated"))
    from crypto_utils import generate_keypair, sign_model_package
    from versioning import ModelMetadata

    sign_priv, sign_pub = generate_keypair()
    model_blob = b"valid-onnx"
    meta = ModelMetadata(version=1, base_round=0, created_at=1.0, schema_version="1.0", rollback_of=None)
    meta_bytes = meta.to_bytes()
    sig = sign_model_package(model_blob, meta_bytes, sign_priv)

    with tempfile.TemporaryDirectory() as d:
        pkg_dir = Path(d)
        pkg_dir.joinpath("package.json").write_text(
            json.dumps({
                "model_blob_b64": base64.b64encode(model_blob).decode(),
                "metadata": {"version": 1, "base_round": 0, "created_at": 1.0, "schema_version": "1.0", "rollback_of": None},
                "signature_b64": base64.b64encode(sig).decode(),
            })
        )
        pubkey_path = pkg_dir / "pub.pem"
        pubkey_path.write_bytes(sign_pub)
        r = subprocess.run([sys.executable, str(SCRIPT), str(pkg_dir), str(pubkey_path)], capture_output=True)
    assert r.returncode == 0
