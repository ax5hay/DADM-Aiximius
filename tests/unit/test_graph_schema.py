"""Unit tests for graph schema helpers."""
from __future__ import annotations

import sys
from pathlib import Path

# Add graph to path when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "graph"))

from schema import (
    cluster_id,
    device_node_id,
    event_id,
    subject_id,
    window_id,
)


def test_device_node_id() -> None:
    assert device_node_id("abc") == "did:abc"
    assert device_node_id("uuid-123") == "did:uuid-123"


def test_event_id() -> None:
    assert event_id("ev1") == "evt:ev1"


def test_cluster_id() -> None:
    assert "clu:" in cluster_id(12345.0)
    assert "default" in cluster_id(12345.0)
    assert "hash" in cluster_id(12345.0, "hash")


def test_window_id() -> None:
    assert window_id(1000.0, 60) == "win:1000:60"


def test_subject_id() -> None:
    assert subject_id("label", "part") == "subj:label:part"
