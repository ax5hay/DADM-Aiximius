//! Network flow summaries. Cross-platform best-effort (e.g. sysinfo connections).

use super::{Event, EventKind, NetworkEvent};
use sysinfo::System;
use std::sync::Mutex;

pub struct NetworkCollector {
    sys: Mutex<System>,
}

impl Default for NetworkCollector {
    fn default() -> Self {
        Self {
            sys: Mutex::new(System::new_all()),
        }
    }
}

impl NetworkCollector {
    /// Snapshot network connections as flow summary events
    pub fn snapshot(&self) -> Result<Vec<Event>, std::io::Error> {
        let mut sys = self.sys.lock().map_err(|_| std::io::ErrorKind::Other)?;
        sys.refresh_networks_list();
        sys.refresh_networks();

        let mut events = Vec::new();
        for (iface, data) in sys.networks() {
            let event = NetworkEvent {
                local_addr: Some(iface.addr().to_string()),
                local_port: None,
                remote_addr: None,
                remote_port: None,
                protocol: iface.name().to_string(),
                bytes_sent: data.received(),
                bytes_recv: data.transmitted(),
                pid: None,
            };
            events.push(Event::new(EventKind::Network(event), "network"));
        }
        Ok(events)
    }
}
