//! Process execution metadata collector (cross-platform via sysinfo).

use super::{Event, EventKind, ProcessEvent};
use sysinfo::System;
use std::sync::Mutex;

pub struct ProcessCollector {
    interval_secs: u64,
    sys: Mutex<System>,
}

impl ProcessCollector {
    pub fn new(interval_secs: u64) -> Self {
        Self {
            interval_secs,
            sys: Mutex::new(System::new_all()),
        }
    }

    /// Snapshot current processes as events (execution metadata)
    pub fn snapshot(&self) -> Result<Vec<Event>, std::io::Error> {
        let mut sys = self.sys.lock().map_err(|_| std::io::ErrorKind::Other)?;
        sys.refresh_all();
        sys.refresh_processes();

        let mut events = Vec::new();
        for (pid, proc_) in sys.processes() {
            let exe = proc_.exe().and_then(|p| p.to_str().map(String::from));
            let cmd = proc_.cmd().first().cloned().unwrap_or_else(|| proc_.name().to_string());
            let event = ProcessEvent {
                pid: pid.as_u32(),
                ppid: proc_.parent().map(|p| p.as_u32()),
                name: proc_.name().to_string(),
                exe,
                cmdline: Some(cmd),
                uid: None, // sysinfo doesn't provide; platform layer can fill
                started_at: None,
            };
            events.push(Event::new(EventKind::Process(event), "process"));
        }
        Ok(events)
    }
}
