//! Statistical behavioral feature extraction from raw events.

mod pipeline;
mod behavioral;

pub use pipeline::{FeatureExtractor, FeaturePipeline};
pub use behavioral::BehavioralStats;

use serde::{Deserialize, Serialize};

/// Fixed-size feature vector for model input (e.g. 64-dim)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeatureVector {
    pub dim: usize,
    pub values: Vec<f32>,
    pub event_id: String,
    pub ts: i64,
}

impl FeatureVector {
    pub fn as_slice(&self) -> &[f32] {
        &self.values[..self.dim.min(self.values.len())]
    }
}
