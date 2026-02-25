//! Uplink client: report device, events, and risk scores to graph/fusion API.

use crate::collectors::Event;
use crate::config::UplinkConfig;
use crate::risk::{RiskLevel, RiskResult};
use chrono::Utc;
use serde::Serialize;
use std::time::Duration;
use tracing::{info, warn};

fn level_str(level: RiskLevel) -> &'static str {
    match level {
        RiskLevel::Low => "low",
        RiskLevel::Medium => "medium",
        RiskLevel::High => "high",
    }
}

fn ts_iso(ms: i64) -> String {
    let dt = Utc.timestamp_millis_opt(ms).single().unwrap_or_else(Utc::now);
    dt.to_rfc3339()
}

/// Payloads for graph API (align with graph/schema and ingest endpoints).
#[derive(Serialize)]
struct DevicePayload {
    node_id: String,
    platform: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    first_seen: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    last_seen: Option<String>,
}

#[derive(Serialize)]
struct EventPayload {
    event_id: String,
    kind: String,
    ts: String,
    device_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    payload_hash: Option<String>,
}

#[derive(Serialize)]
struct RiskPayload {
    id: String,
    score: f32,
    level: String,
    ts: String,
    window_start: String,
    window_end: String,
    source: String,
}

pub struct UplinkClient {
    config: UplinkConfig,
    client: reqwest::blocking::Client,
    base_url: String,
    device_id: String,
    device_registered: std::sync::atomic::AtomicBool,
}

impl UplinkClient {
    /// Device node id (e.g. did:local-device) sent to graph.
    pub fn device_id(&self) -> &str {
        &self.device_id
    }

    pub fn new(config: UplinkConfig) -> Option<Self> {
        let endpoint = config.endpoint.as_ref()?.trim_end_matches('/');
        let device_id = config
            .device_id
            .clone()
            .unwrap_or_else(|| "local-device".to_string());
        let node_id = if device_id.starts_with("did:") {
            device_id.clone()
        } else {
            format!("did:{}", device_id)
        };
        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(15))
            .connect_timeout(Duration::from_secs(5))
            .build()
            .ok()?;
        Some(Self {
            config,
            client,
            base_url: endpoint.to_string(),
            device_id: node_id,
            device_registered: std::sync::atomic::AtomicBool::new(false),
        })
    }

    fn post<T: Serialize + ?Sized>(&self, path: &str, body: &T) -> Result<(), String> {
        let url = format!("{}{}", self.base_url, path);
        let res = self
            .client
            .post(&url)
            .json(body)
            .send()
            .map_err(|e| e.to_string())?;
        if !res.status().is_success() {
            let status = res.status();
            let text = res.text().unwrap_or_default();
            return Err(format!("{} {}", status, text));
        }
        Ok(())
    }

    /// Register device once (idempotent).
    pub fn ensure_device(&self, platform: &str) {
        if self
            .device_registered
            .load(std::sync::atomic::Ordering::Relaxed)
        {
            return;
        }
        let now = Utc::now().to_rfc3339();
        let payload = DevicePayload {
            node_id: self.device_id.clone(),
            platform: platform.to_string(),
            first_seen: Some(now.clone()),
            last_seen: Some(now),
        };
        if self.post("/api/v1/devices", &payload).is_ok() {
            self.device_registered
                .store(true, std::sync::atomic::Ordering::Relaxed);
            info!(device_id = %self.device_id, "uplink device registered");
        } else {
            warn!(device_id = %self.device_id, "uplink device registration failed");
        }
    }

    /// Report events and one risk result to graph API. Events are sent one-by-one; risk score once.
    pub fn report(
        &self,
        platform: &str,
        events: &[Event],
        risk: &RiskResult,
    ) -> Result<(), String> {
        self.ensure_device(platform);

        for ev in events {
            let kind = match &ev.kind {
                crate::collectors::EventKind::Process(_) => "process",
                crate::collectors::EventKind::Network(_) => "network",
                crate::collectors::EventKind::FileIntegrity(_) => "file_integrity",
                crate::collectors::EventKind::Privilege(_) => "privilege",
            };
            let payload = EventPayload {
                event_id: ev.id.clone(),
                kind: kind.to_string(),
                ts: ev.ts.to_rfc3339(),
                device_id: self.device_id.clone(),
                payload_hash: None,
            };
            if let Err(e) = self.post("/api/v1/events", &payload) {
                warn!(event_id = %ev.id, error = %e, "uplink event failed");
            }
        }

        let window_sec = 60i64;
        let window_start_ms = risk.ts - window_sec * 1000;
        let payload = RiskPayload {
            id: format!("risk_{}_{}", self.device_id, risk.ts),
            score: risk.score,
            level: level_str(risk.level).to_string(),
            ts: ts_iso(risk.ts),
            window_start: ts_iso(window_start_ms),
            window_end: ts_iso(risk.ts),
            source: self.device_id.clone(), // so graph can link HAS_RISK_IN to device
        };
        self.post("/api/v1/risk_scores", &payload)?;
        info!(score = risk.score, level = ?risk.level, "uplink risk reported");
        Ok(())
    }
}
