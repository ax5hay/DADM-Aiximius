//! Privilege escalation attempt detection.
//! Platform-specific: audit logs, setuid binaries, sudo. Stub for cross-platform compile.

use super::{Event, EventKind, PrivilegeEvent};
use std::sync::Mutex;
use std::collections::VecDeque;

/// In production: parse audit logs (Linux), ETW (Windows), or similar.
/// Here we use a stub that can be fed by platform-specific hooks.
pub struct PrivilegeCollector {
    recent: Mutex<VecDeque<PrivilegeEvent>>,
}

impl Default for PrivilegeCollector {
    fn default() -> Self {
        Self {
            recent: Mutex::new(VecDeque::new()),
        }
    }
}

impl PrivilegeCollector {
    /// Record a privilege event (call from platform layer when e.g. setuid/sudo detected)
    pub fn record(&self, e: PrivilegeEvent) {
        if let Ok(mut q) = self.recent.lock() {
            q.push_back(e);
            if q.len() > 1000 {
                q.pop_front();
            }
        }
    }

    /// Snapshot: return recent privilege events as unified Events
    pub fn snapshot(&self) -> Result<Vec<Event>, std::io::Error> {
        let mut q = self.recent.lock().map_err(|_| std::io::ErrorKind::Other)?;
        let out: Vec<Event> = q.drain(..).map(|e| Event::new(EventKind::Privilege(e), "privilege")).collect();
        Ok(out)
    }
}
