//! Agent configuration. Uplink is server-controlled (Aiximius), not user.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    /// Data directory (encrypted store, model cache)
    pub data_dir: PathBuf,
    /// Path to ONNX anomaly detection model
    pub model_path: PathBuf,
    /// Enable collectors
    pub collectors: CollectorsConfig,
    /// Feature extraction parameters
    pub features: FeaturesConfig,
    /// Risk scoring thresholds
    pub risk: RiskConfig,
    /// Uplink: controlled by Aiximius server policy, not user preference
    pub uplink: UplinkConfig,
    /// Logging
    pub log: LogConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollectorsConfig {
    pub process: bool,
    pub network: bool,
    pub file_integrity: bool,
    pub privilege: bool,
    /// Process poll interval (seconds)
    pub process_interval_secs: u64,
    /// File scan interval (seconds)
    pub file_interval_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeaturesConfig {
    /// Sliding window size for behavioral stats
    pub window_events: usize,
    /// Number of numerical features expected by model
    pub feature_dim: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskConfig {
    /// Score above this is high risk (0.0–1.0)
    pub high_threshold: f32,
    /// Score above this is medium risk
    pub medium_threshold: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UplinkConfig {
    /// Whether uplink is enabled (set by Aiximius server policy, not user)
    pub enabled: bool,
    /// Endpoint URL when enabled
    pub endpoint: Option<String>,
    /// Report interval seconds when enabled
    pub report_interval_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogConfig {
    pub level: String,
    pub json: bool,
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            data_dir: PathBuf::from(".dadm"),
            model_path: PathBuf::from("model.onnx"),
            collectors: CollectorsConfig::default(),
            features: FeaturesConfig::default(),
            risk: RiskConfig::default(),
            uplink: UplinkConfig::default(),
            log: LogConfig::default(),
        }
    }
}

impl Default for CollectorsConfig {
    fn default() -> Self {
        Self {
            process: true,
            network: true,
            file_integrity: true,
            privilege: true,
            process_interval_secs: 5,
            file_interval_secs: 60,
        }
    }
}

impl Default for FeaturesConfig {
    fn default() -> Self {
        Self {
            window_events: 100,
            feature_dim: 64,
        }
    }
}

impl Default for RiskConfig {
    fn default() -> Self {
        Self {
            high_threshold: 0.8,
            medium_threshold: 0.5,
        }
    }
}

impl Default for UplinkConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            endpoint: None,
            report_interval_secs: 300,
        }
    }
}

impl Default for LogConfig {
    fn default() -> Self {
        Self {
            level: "info".to_string(),
            json: true,
        }
    }
}

impl AgentConfig {
    /// Load from JSON file if present; otherwise return default
    pub fn load(path: &std::path::Path) -> Self {
        if path.exists() {
            if let Ok(data) = std::fs::read_to_string(path) {
                if let Ok(c) = serde_json::from_str::<AgentConfig>(&data) {
                    return c;
                }
            }
        }
        Self::default()
    }
}
