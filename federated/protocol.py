"""
Federated protocol message types and (de)serialization.
No raw logs; only encrypted gradient updates and signed model packages.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class ConfigResponse:
    current_round: int
    model_version: int
    server_public_key: str  # PEM
    min_clients: int
    grace_seconds: int
    schema_version: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ConfigResponse":
        return cls(**{k: d[k] for k in ("current_round", "model_version", "server_public_key", "min_clients", "grace_seconds", "schema_version")})


@dataclass
class UpdateRequest:
    client_id: str
    round: int
    encrypted_payload: str  # base64
    compression_meta: dict  # for server to decompress after decrypt
    signature: str  # base64
    schema_version: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "UpdateRequest":
        return cls(
            client_id=d["client_id"],
            round=int(d["round"]),
            encrypted_payload=d["encrypted_payload"],
            compression_meta=d.get("compression_meta", {}),
            signature=d["signature"],
            schema_version=d.get("schema_version", "1.0"),
        )


@dataclass
class ModelPackageResponse:
    version: int
    model_blob_b64: str
    metadata: dict
    signature_b64: str

    def to_dict(self) -> dict:
        return asdict(self)
