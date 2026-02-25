"""
Model versioning: monotonic version, metadata, rollback pointer.
Server stores immutable artifacts; clients keep current + previous for rollback.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ModelMetadata:
    version: int
    base_round: int
    created_at: float
    schema_version: str
    rollback_of: Optional[int] = None  # if set, this package is the rollback target version

    def to_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True).encode("utf-8")

    @classmethod
    def from_bytes(cls, b: bytes) -> "ModelMetadata":
        return cls(**json.loads(b.decode("utf-8")))


def next_version(current: int) -> int:
    return current + 1


def package_path(base_dir: Path, version: int) -> tuple[Path, Path, Path]:
    """Returns (model_path, meta_path, sig_path)."""
    base_dir = Path(base_dir)
    return (
        base_dir / f"model_v{version}.onnx",
        base_dir / f"model_v{version}.meta.json",
        base_dir / f"model_v{version}.sig",
    )


def save_package(base_dir: Path, version: int, model_blob: bytes, metadata: ModelMetadata, signature: bytes) -> None:
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    mp, metap, sigp = package_path(base_dir, version)
    mp.write_bytes(model_blob)
    metap.write_text(json.dumps(asdict(metadata), indent=2))
    sigp.write_bytes(signature)


def load_package(base_dir: Path, version: int) -> tuple[bytes, ModelMetadata, bytes]:
    mp, metap, sigp = package_path(base_dir, version)
    return mp.read_bytes(), ModelMetadata(**json.loads(metap.read_text())), sigp.read_bytes()
