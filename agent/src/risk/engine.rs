//! Combines anomaly score from model with configurable thresholds; produces risk level.

use crate::config::RiskConfig;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RiskLevel {
    Low,
    Medium,
    High,
}

impl RiskLevel {
    pub fn from_score(score: f32, config: &RiskConfig) -> Self {
        if score >= config.high_threshold {
            RiskLevel::High
        } else if score >= config.medium_threshold {
            RiskLevel::Medium
        } else {
            RiskLevel::Low
        }
    }
}

/// Risk result for a single event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskResult {
    pub event_id: String,
    pub score: f32,
    pub level: RiskLevel,
    pub ts: i64,
}

pub struct RiskEngine {
    config: RiskConfig,
}

impl RiskEngine {
    pub fn new(config: RiskConfig) -> Self {
        Self { config }
    }

    pub fn score(&self, event_id: String, raw_score: f32, ts: i64) -> RiskResult {
        let level = RiskLevel::from_score(raw_score, &self.config);
        RiskResult {
            event_id,
            score: raw_score,
            level,
            ts,
        }
    }

    pub fn config(&self) -> &RiskConfig {
        &self.config
    }
}
