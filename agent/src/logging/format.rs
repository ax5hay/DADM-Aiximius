//! JSON log lines: one JSON object per line (ndjson) for ingestion and audit.

use serde::Serialize;
use std::io::Write;
use tracing_subscriber::fmt::format::FmtSpan;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;

#[derive(Serialize)]
pub struct LogEvent<'a> {
    pub ts: String,
    pub level: &'a str,
    pub target: &'a str,
    pub message: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_id: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub risk_score: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub risk_level: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kind: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<&'a str>,
}

/// Initialize tracing with JSON format (one JSON object per line)
pub struct StructuredLogger;

impl StructuredLogger {
    /// Install global subscriber: JSON lines to stdout, level from RUST_LOG or default.
    pub fn init(json: bool, default_level: &str) {
        let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(default_level));
        if json {
            let fmt = tracing_subscriber::fmt::layer()
                .json()
                .with_span_events(FmtSpan::NONE)
                .with_writer(std::io::stdout);
            tracing_subscriber::registry()
                .with(filter)
                .with(fmt)
                .init();
        } else {
            tracing_subscriber::registry()
                .with(filter)
                .with(tracing_subscriber::fmt::layer().with_writer(std::io::stdout))
                .init();
        }
    }

    /// Emit a single structured log line (e.g. for risk result) without going through tracing
    pub fn emit_json(event: &impl Serialize, w: &mut impl Write) {
        if let Ok(line) = serde_json::to_string(event) {
            let _ = writeln!(w, "{}", line);
        }
    }
}
