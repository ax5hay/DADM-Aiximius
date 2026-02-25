#!/usr/bin/env python3
"""
Export a signed model package to a directory or archive for air-gapped transfer.
Verify on the other side with server /model/verify or a standalone script.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from versioning import load_package


def main():
    p = argparse.ArgumentParser(description="Export signed model package for air-gap")
    p.add_argument("--registry", type=Path, default=Path("registry"))
    p.add_argument("--version", type=int, default=None)
    p.add_argument("--output", type=Path, default=Path("signed_package"))
    args = p.parse_args()

    # Use latest if no version
    if args.version is None:
        versions = [f.stem.replace("model_v", "") for f in args.registry.glob("model_v*.onnx")]
        versions = sorted([int(v) for v in versions if v.isdigit()])
        args.version = versions[-1] if versions else 0

    model_blob, metadata, sig = load_package(args.registry, args.version)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "model.onnx").write_bytes(model_blob)
    (args.output / "metadata.json").write_text(json.dumps({
        "version": metadata.version,
        "base_round": metadata.base_round,
        "created_at": metadata.created_at,
        "schema_version": metadata.schema_version,
        "rollback_of": metadata.rollback_of,
    }, indent=2))
    (args.output / "signature.bin").write_bytes(sig)
    (args.output / "package.json").write_text(json.dumps({
        "model_blob_b64": base64.b64encode(model_blob).decode(),
        "metadata": json.loads(metadata.to_bytes().decode()),
        "signature_b64": base64.b64encode(sig).decode(),
    }, indent=2))
    print(f"Exported version {args.version} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
