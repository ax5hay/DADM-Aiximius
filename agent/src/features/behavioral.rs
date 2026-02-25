//! Behavioral statistics over a sliding window of events.

use crate::collectors::{Event, EventKind};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BehavioralStats {
    /// Counts per event type in window
    pub process_count: u32,
    pub network_count: u32,
    pub file_count: u32,
    pub privilege_count: u32,
    /// Process: unique exe names, cmdline length stats
    pub unique_process_names: u32,
    pub avg_cmdline_len: f32,
    /// Network: total bytes, connection count
    pub total_bytes_sent: u64,
    pub total_bytes_recv: u64,
    /// File: unique paths, total size hashed
    pub unique_file_paths: u32,
    pub total_file_size: u64,
    /// Privilege: escalation attempts (success/fail)
    pub privilege_success: u32,
    pub privilege_fail: u32,
}

impl BehavioralStats {
    pub fn from_events(events: &[Event]) -> Self {
        let mut s = BehavioralStats::default();
        let mut cmdline_lens: Vec<usize> = Vec::new();
        let mut process_names = std::collections::HashSet::new();
        let mut file_paths = std::collections::HashSet::new();

        for e in events {
            match &e.kind {
                EventKind::Process(p) => {
                    s.process_count += 1;
                    process_names.insert(p.name.clone());
                    if let Some(ref c) = p.cmdline {
                        cmdline_lens.push(c.len());
                    }
                }
                EventKind::Network(n) => {
                    s.network_count += 1;
                    s.total_bytes_sent += n.bytes_sent;
                    s.total_bytes_recv += n.bytes_recv;
                }
                EventKind::FileIntegrity(f) => {
                    s.file_count += 1;
                    file_paths.insert(f.path.clone());
                    s.total_file_size += f.size;
                }
                EventKind::Privilege(p) => {
                    s.privilege_count += 1;
                    if p.success {
                        s.privilege_success += 1;
                    } else {
                        s.privilege_fail += 1;
                    }
                }
            }
        }

        s.unique_process_names = process_names.len() as u32;
        s.unique_file_paths = file_paths.len() as u32;
        s.avg_cmdline_len = if cmdline_lens.is_empty() {
            0.0
        } else {
            cmdline_lens.iter().sum::<usize>() as f32 / cmdline_lens.len() as f32
        };
        s
    }

    /// Encode to fixed-dim f32 vector for model input (normalized)
    pub fn to_vector(&self, dim: usize) -> Vec<f32> {
        let raw: Vec<f32> = vec![
            self.process_count as f32 / 1000.0,
            self.network_count as f32 / 1000.0,
            self.file_count as f32 / 1000.0,
            self.privilege_count as f32 / 100.0,
            self.unique_process_names as f32 / 500.0,
            self.avg_cmdline_len / 1000.0,
            (self.total_bytes_sent as f64 / 1e9).min(1.0) as f32,
            (self.total_bytes_recv as f64 / 1e9).min(1.0) as f32,
            self.unique_file_paths as f32 / 1000.0,
            (self.total_file_size as f64 / 1e9).min(1.0) as f32,
            self.privilege_success as f32 / 100.0,
            self.privilege_fail as f32 / 100.0,
        ];
        // Pad or truncate to dim
        let mut out = vec![0.0f32; dim];
        let copy = raw.len().min(dim);
        out[..copy].copy_from_slice(&raw[..copy]);
        out
    }
}
