//! Event collectors: process, network, file integrity, privilege.
//! Platform-specific implementations where needed; shared event types.

mod process;
mod network;
mod file;
mod privilege;

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use uuid::Uuid;

pub use process::ProcessCollector;
pub use network::NetworkCollector;
pub use file::FileIntegrityCollector;
pub use privilege::PrivilegeCollector;

/// Unified event from any collector
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    pub id: String,
    pub ts: DateTime<Utc>,
    pub kind: EventKind,
    pub source: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum EventKind {
    Process(ProcessEvent),
    Network(NetworkEvent),
    FileIntegrity(FileIntegrityEvent),
    Privilege(PrivilegeEvent),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessEvent {
    pub pid: u32,
    pub ppid: Option<u32>,
    pub name: String,
    pub exe: Option<String>,
    pub cmdline: Option<String>,
    pub uid: Option<u32>,
    pub started_at: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkEvent {
    pub local_addr: Option<String>,
    pub local_port: Option<u16>,
    pub remote_addr: Option<String>,
    pub remote_port: Option<u16>,
    pub protocol: String,
    pub bytes_sent: u64,
    pub bytes_recv: u64,
    pub pid: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileIntegrityEvent {
    pub path: String,
    pub hash_sha256: String,
    pub size: u64,
    pub modified_ts: Option<i64>,
    pub event: FileIntegrityChange,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FileIntegrityChange {
    Created,
    Modified,
    Deleted,
    Scanned,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrivilegeEvent {
    pub pid: u32,
    pub from_uid: u32,
    pub to_uid: Option<u32>,
    pub success: bool,
    pub method: String,
}

impl Event {
    pub fn new(kind: EventKind, source: impl Into<String>) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            ts: Utc::now(),
            kind,
            source: source.into(),
            metadata: None,
        }
    }
}

/// Orchestrates all collectors and yields unified events (e.g. via channel)
pub struct CollectorPipeline {
    pub process: ProcessCollector,
    pub network: NetworkCollector,
    pub file: FileIntegrityCollector,
    pub privilege: PrivilegeCollector,
}

impl CollectorPipeline {
    pub fn new(config: &crate::config::CollectorsConfig) -> Self {
        Self {
            process: ProcessCollector::new(config.process_interval_secs),
            network: NetworkCollector::default(),
            file: FileIntegrityCollector::new(config.file_interval_secs),
            privilege: PrivilegeCollector::default(),
        }
    }

    /// Collect current snapshot of events (polling). In production, would be driven by OS hooks.
    pub fn collect_snapshot(&self) -> Vec<Event> {
        let mut out = Vec::new();
        if let Ok(events) = self.process.snapshot() {
            out.extend(events);
        }
        if let Ok(events) = self.network.snapshot() {
            out.extend(events);
        }
        if let Ok(events) = self.file.snapshot() {
            out.extend(events);
        }
        if let Ok(events) = self.privilege.snapshot() {
            out.extend(events);
        }
        out
    }
}
