//! File integrity hashes (scan paths, emit hash + metadata).

use super::{Event, EventKind, FileIntegrityEvent, FileIntegrityChange};
use sha2::{Sha256, Digest};
use std::path::Path;
use std::sync::Mutex;
use walkdir::WalkDir;
use std::collections::HashSet;

const MAX_FILES_PER_SNAPSHOT: usize = 500;
const MAX_DEPTH: usize = 4;

pub struct FileIntegrityCollector {
    interval_secs: u64,
    /// Paths to watch (default: temp and home sample)
    watch_paths: Mutex<Vec<std::path::PathBuf>>,
    last_hashes: Mutex<HashSet<String>>,
}

impl FileIntegrityCollector {
    pub fn new(interval_secs: u64) -> Self {
        Self {
            interval_secs,
            watch_paths: Mutex::new(Self::default_paths()),
            last_hashes: Mutex::new(HashSet::new()),
        }
    }

    fn default_paths() -> Vec<std::path::PathBuf> {
        let mut p = Vec::new();
        if let Some(home) = dirs::home_dir() {
            p.push(home.join(".config"));
            p.push(home.join(".local").join("share"));
        }
        if let Some(tmp) = std::env::temp_dir().to_str() {
            p.push(std::path::PathBuf::from(tmp));
        }
        p
    }

    pub fn add_path(&self, path: std::path::PathBuf) {
        if let Ok(mut paths) = self.watch_paths.lock() {
            paths.push(path);
        }
    }

    fn hash_file(path: &Path) -> Option<String> {
        let data = std::fs::read(path).ok()?;
        let mut h = Sha256::new();
        h.update(&data);
        Some(format!("{:x}", h.finalize()))
    }

    pub fn snapshot(&self) -> Result<Vec<Event>, std::io::Error> {
        let paths = self.watch_paths.lock().map_err(|_| std::io::ErrorKind::Other)?;
        let mut last = self.last_hashes.lock().map_err(|_| std::io::ErrorKind::Other)?;
        let mut events = Vec::new();
        let mut current_hashes = HashSet::new();

        for root in paths.iter() {
            if !root.exists() {
                continue;
            }
            for entry in WalkDir::new(root)
                .max_depth(MAX_DEPTH)
                .follow_links(false)
                .into_iter()
                .filter_map(|e| e.ok())
            {
                if events.len() >= MAX_FILES_PER_SNAPSHOT {
                    break;
                }
                let path = entry.path();
                if path.is_dir() {
                    continue;
                }
                let path_str = path.to_string_lossy().to_string();
                let (hash, size, modified) = match Self::hash_file(path) {
                    Some(h) => {
                        let m = std::fs::metadata(path).ok();
                        let size = m.as_ref().map(|m| m.len()).unwrap_or(0);
                        let modified = m.and_then(|m| m.modified().ok()).and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok().map(|d| d.as_secs() as i64));
                        (h, size, modified)
                    }
                    None => continue,
                };
                current_hashes.insert(path_str.clone());
                let change = if last.contains(&path_str) {
                    FileIntegrityChange::Scanned
                } else {
                    FileIntegrityChange::Scanned
                };
                let ev = FileIntegrityEvent {
                    path: path_str,
                    hash_sha256: hash,
                    size,
                    modified_ts: modified,
                    event: change,
                };
                events.push(Event::new(EventKind::FileIntegrity(ev), "file_integrity"));
            }
        }
        *last = current_hashes;
        Ok(events)
    }
}
