//! DADM Agent entrypoint: offline-first, optional uplink (Aiximius-controlled).

use dadm_agent::{
    config::AgentConfig,
    collectors::CollectorPipeline,
    features::FeatureExtractor,
    model::OnnxDetector,
    storage::SecureStore,
    risk::{RiskEngine, RiskLevel},
    logging::StructuredLogger,
};
use std::path::Path;
use std::sync::Arc;
use tracing::info;

fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let config_path = Path::new("config.json");
    let config = AgentConfig::load(config_path);

    StructuredLogger::init(config.log.json, &config.log.level);

    info!(data_dir = ?config.data_dir, "DADM agent starting");

    std::fs::create_dir_all(&config.data_dir)?;
    let store_path = config.data_dir.join("store.db");
    let secret = b"device-secret-placeholder"; // In production: from Secure Enclave / Keystore
    let store = Arc::new(SecureStore::open(&store_path, secret)?);

    let collectors = CollectorPipeline::new(&config.collectors);
    let features = Arc::new(FeatureExtractor::new(config.features.clone()));
    let model = Arc::new(OnnxDetector::load(&config.model_path, config.features.feature_dim)?);
    let risk_engine = RiskEngine::new(config.risk.clone());

    // Single collection cycle: snapshot → features → inference → risk → store
    let events = collectors.collect_snapshot();
    info!(count = events.len(), "collected events");

    let feature_vectors = features.push(events.clone());
    let score = feature_vectors
        .first()
        .map(|fv| model.predict(fv))
        .unwrap_or(0.0);
    let result = feature_vectors
        .first()
        .map(|fv| risk_engine.score(fv.event_id.clone(), score, fv.ts))
        .unwrap_or_else(|| risk_engine.score(String::new(), score, 0));

    for ev in &events {
        let payload = serde_json::to_string(ev)?;
        store.insert_event(
            &ev.id,
            ev.ts.timestamp_millis(),
            ev.source.as_str(),
            &payload,
            Some(result.score),
        )?;
    }
    if result.level != RiskLevel::Low {
        info!(
            event_id = %result.event_id,
            score = result.score,
            level = ?result.level,
            "risk result"
        );
    }

    info!("DADM agent cycle complete");
    Ok(())
}
