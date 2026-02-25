"""
Defense Systems Ontology (DSO) — schema and node ID conventions.
Aligns with docs/DSO-ONTOLOGY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def device_node_id(uuid_or_hash: str) -> str:
    return f"did:{uuid_or_hash}"


def event_id(uuid_or_hash: str) -> str:
    return f"evt:{uuid_or_hash}"


def cluster_id(created_ts: float, method_hash: str = "") -> str:
    return f"clu:{int(created_ts)}:{method_hash or 'default'}"


def window_id(start_ts: float, duration_sec: int) -> str:
    return f"win:{int(start_ts)}:{duration_sec}"


def subject_id(label: str, id_part: str) -> str:
    return f"subj:{label}:{id_part}"


@dataclass
class Device:
    node_id: str
    platform: str  # android | ios | windows | macos | linux
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    mesh_id: Optional[str] = None


@dataclass
class Event:
    event_id: str
    kind: str  # process | network | file_integrity | privilege
    ts: datetime
    device_id: str
    payload_hash: Optional[str] = None


@dataclass
class RiskScore:
    id: str
    score: float
    level: str  # low | medium | high
    ts: datetime
    window_start: datetime
    window_end: datetime
    source: str  # event_id or device_id


@dataclass
class TimeWindow:
    window_id: str
    start_ts: datetime
    end_ts: datetime
    duration_sec: int


@dataclass
class Cluster:
    cluster_id: str
    created_at: datetime
    method: str
    size: int


@dataclass
class SurveillanceSubject:
    subject_id: str
    label: str
    policy: str = "non_intrusive"
