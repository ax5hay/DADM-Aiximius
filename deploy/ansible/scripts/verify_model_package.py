#!/usr/bin/env python3
"""
Verify DADM signed model package. Exit 0 only if signature is valid.
Usage: verify_model_package.py <package_dir> <signing_public_key.pem>
Package dir must contain package.json with model_blob_b64, metadata, signature_b64.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:
    print("cryptography required: pip install cryptography", file=sys.stderr)
    sys.exit(2)


def verify_signature(payload: bytes, signature: bytes, public_key_pem: bytes) -> bool:
    try:
        pub = serialization.load_pem_public_key(public_key_pem, backend=default_backend())
        h = hashes.Hash(hashes.SHA256(), default_backend())
        h.update(payload)
        digest = h.finalize()
        pub.verify(signature, digest, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: verify_model_package.py <package_dir> <signing_public_key.pem>", file=sys.stderr)
        return 2

    pkg_dir = Path(sys.argv[1])
    pubkey_path = Path(sys.argv[2])
    pkg_json = pkg_dir / "package.json"

    if not pkg_json.exists():
        print(f"Missing {pkg_json}", file=sys.stderr)
        return 2
    if not pubkey_path.exists():
        print(f"Missing {pubkey_path}", file=sys.stderr)
        return 2

    try:
        pkg = json.loads(pkg_json.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Invalid package.json: {e}", file=sys.stderr)
        return 2

    model_b64 = pkg.get("model_blob_b64")
    meta = pkg.get("metadata")
    sig_b64 = pkg.get("signature_b64")
    if not all([model_b64, meta is not None, sig_b64]):
        print("package.json must contain model_blob_b64, metadata, signature_b64", file=sys.stderr)
        return 2

    try:
        model_blob = base64.b64decode(model_b64)
        sig = base64.b64decode(sig_b64)
    except Exception as e:
        print(f"Invalid base64: {e}", file=sys.stderr)
        return 1

    metadata_bytes = json.dumps(meta, sort_keys=True).encode("utf-8")
    payload = model_blob + metadata_bytes
    pubkey_pem = pubkey_path.read_bytes()

    if not verify_signature(payload, sig, pubkey_pem):
        print("Signature verification failed", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
