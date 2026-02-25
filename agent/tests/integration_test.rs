//! Integration test: config load, pipeline run, feature extract, risk score, uplink, no model.

use dadm_agent::{
    config::{AgentConfig, UplinkConfig},
    collectors::CollectorPipeline,
    features::FeatureExtractor,
    model::OnnxDetector,
    risk::{RiskEngine, RiskLevel},
    storage::SecureStore,
    uplink::UplinkClient,
};
use std::path::Path;

#[test]
fn config_load_default() {
    let c = AgentConfig::load(Path::new("nonexistent.json"));
    assert_eq!(c.features.feature_dim, 64);
    assert!(!c.uplink.enabled);
}

#[test]
fn pipeline_collect_and_features() {
    let config = dadm_agent::config::CollectorsConfig::default();
    let pipeline = CollectorPipeline::new(&config);
    let events = pipeline.collect_snapshot();
    let extractor = FeatureExtractor::new(dadm_agent::config::FeaturesConfig::default());
    let vectors = extractor.push(events);
    // May be 0 if no events, or 1 if we got a window
    assert!(vectors.len() <= 1);
}

#[test]
fn risk_engine_thresholds() {
    let config = dadm_agent::config::RiskConfig::default();
    let engine = RiskEngine::new(config);
    let r_low = engine.score("e1".into(), 0.3, 0);
    let r_med = engine.score("e2".into(), 0.6, 0);
    let r_high = engine.score("e3".into(), 0.9, 0);
    assert_eq!(r_low.level, RiskLevel::Low);
    assert_eq!(r_med.level, RiskLevel::Medium);
    assert_eq!(r_high.level, RiskLevel::High);
}

#[test]
fn onnx_no_model_returns_zero() {
    let d = OnnxDetector::load(Path::new("nonexistent.onnx"), 64).unwrap();
    let fv = dadm_agent::FeatureVector {
        dim: 64,
        values: vec![0.0; 64],
        event_id: "t".into(),
        ts: 0,
    };
    assert_eq!(d.predict(&fv), 0.0);
}

#[test]
fn storage_roundtrip() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("store.db");
    let store = SecureStore::open(&path, b"test-secret").unwrap();
    store
        .insert_event("id1", 123, "process", r#"{"x":1}"#, Some(0.5))
        .unwrap();
    let out = store.get_event("id1").unwrap();
    assert!(out.is_some());
    let (ts, payload, score) = out.unwrap();
    assert_eq!(ts, 123);
    assert_eq!(payload, r#"{"x":1}"#);
    assert_eq!(score, Some(0.5));
}

#[test]
fn uplink_client_none_when_disabled() {
    let config = UplinkConfig {
        enabled: true,
        endpoint: None,
        report_interval_secs: 300,
        device_id: None,
    };
    assert!(UplinkClient::new(config).is_none());
}

#[test]
fn uplink_client_some_when_endpoint_set() {
    let config = UplinkConfig {
        enabled: true,
        endpoint: Some("http://127.0.0.1:9999".to_string()),
        report_interval_secs: 300,
        device_id: Some("test-device".to_string()),
    };
    let client = UplinkClient::new(config);
    assert!(client.is_some());
    let c = client.unwrap();
    assert!(c.device_id().starts_with("did:"));
    assert!(c.device_id().contains("test-device"));
}

