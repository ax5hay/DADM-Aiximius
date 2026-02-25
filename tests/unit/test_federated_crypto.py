"""Unit tests for federated crypto and versioning."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "federated"))

from crypto_utils import generate_keypair, sign_model_package, verify_model_package
from versioning import ModelMetadata, next_version


def test_next_version() -> None:
    assert next_version(0) == 1
    assert next_version(5) == 6


def test_model_metadata_roundtrip() -> None:
    meta = ModelMetadata(
        version=1,
        base_round=0,
        created_at=123.45,
        schema_version="1.0",
        rollback_of=None,
    )
    b = meta.to_bytes()
    meta2 = ModelMetadata.from_bytes(b)
    assert meta2.version == meta.version
    assert meta2.schema_version == meta.schema_version


def test_verify_model_package() -> None:
    """Sign then verify model package with generated keypair."""
    sign_priv_pem, sign_pub_pem = generate_keypair()
    model_blob = b"fake-onnx-model"
    metadata = ModelMetadata(version=1, base_round=0, created_at=1.0, schema_version="1.0", rollback_of=None)
    meta_bytes = metadata.to_bytes()
    sig = sign_model_package(model_blob, meta_bytes, sign_priv_pem)
    assert verify_model_package(model_blob, meta_bytes, sig, sign_pub_pem) is True
    _, other_pub_pem = generate_keypair()
    assert verify_model_package(model_blob, meta_bytes, sig, other_pub_pem) is False
