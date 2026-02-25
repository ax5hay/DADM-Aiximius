//! DADM Agent — Cross-platform defensive AI endpoint agent.
//!
//! Modular structure:
//! - [`collectors`] — Process, network, file, privilege event collection
//! - [`features`] — Statistical behavioral feature extraction pipeline
//! - [`model`] — ONNX anomaly detection inference
//! - [`storage`] — Encrypted local storage
//! - [`risk`] — Risk scoring engine
//! - [`logging`] — Structured JSON logging

pub mod config;
pub mod collectors;
pub mod features;
pub mod model;
pub mod storage;
pub mod risk;
pub mod logging;

pub use config::AgentConfig;
pub use collectors::{Event, EventKind, CollectorPipeline};
pub use features::{FeatureVector, FeatureExtractor};
pub use model::OnnxDetector;
pub use storage::SecureStore;
pub use risk::RiskEngine;
pub use logging::StructuredLogger;
