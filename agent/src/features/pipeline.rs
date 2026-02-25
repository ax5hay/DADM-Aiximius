//! Feature extraction pipeline: events → sliding window → behavioral stats → vector.

use super::{FeatureVector, BehavioralStats};
use crate::collectors::Event;
use crate::config::FeaturesConfig;
use std::collections::VecDeque;
use std::sync::Mutex;
use chrono::Utc;

pub struct FeatureExtractor {
    config: FeaturesConfig,
    window: Mutex<VecDeque<Event>>,
}

impl FeatureExtractor {
    pub fn new(config: FeaturesConfig) -> Self {
        Self {
            config,
            window: Mutex::new(VecDeque::new()),
        }
    }

    /// Push events into the sliding window and optionally emit a feature vector per event (or batched)
    pub fn push(&self, events: Vec<Event>) -> Vec<FeatureVector> {
        let mut w = self.window.lock().expect("lock");
        for e in events {
            w.push_back(e);
            while w.len() > self.config.window_events {
                w.pop_front();
            }
        }
        let snapshot: Vec<Event> = w.iter().cloned().collect();
        drop(w);

        if snapshot.is_empty() {
            return Vec::new();
        }

        let stats = BehavioralStats::from_events(&snapshot);
        let values = stats.to_vector(self.config.feature_dim);
        let ts = Utc::now().timestamp_millis();
        let event_id = snapshot.last().map(|e| e.id.clone()).unwrap_or_default();
        vec![FeatureVector {
            dim: self.config.feature_dim,
            values: values.clone(),
            event_id,
            ts,
        }]
    }

    /// Get current window stats and produce one feature vector (e.g. after batch)
    pub fn flush(&self) -> Option<FeatureVector> {
        let w = self.window.lock().expect("lock");
        let snapshot: Vec<Event> = w.iter().cloned().collect();
        let event_id = snapshot.last().map(|e| e.id.clone()).unwrap_or_default();
        drop(w);

        if snapshot.is_empty() {
            return None;
        }
        let stats = BehavioralStats::from_events(&snapshot);
        Some(FeatureVector {
            dim: self.config.feature_dim,
            values: stats.to_vector(self.config.feature_dim),
            event_id,
            ts: Utc::now().timestamp_millis(),
        })
    }
}

/// Alias for pipeline that runs: events → features
pub type FeaturePipeline = FeatureExtractor;
