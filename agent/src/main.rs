//! DADM Agent entrypoint: offline-first, optional uplink (Aiximius-controlled).
//! Runs a single cycle or a daemon loop with configurable interval; when uplink is enabled,
//! reports device, events, and risk to the graph API.

use dadm_agent::{
    config::AgentConfig,
    collectors::CollectorPipeline,
    features::FeatureExtractor,
    model::OnnxDetector,
    storage::SecureStore,
    risk::{RiskEngine, RiskLevel},
    logging::StructuredLogger,
    uplink::UplinkClient,
};
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;
use tracing::info;

fn detect_platform() -> &'static str {
    if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else if cfg!(target_os = "android") {
        "android"
    } else {
        "unknown"
    }
}

fn run_one_cycle(
    collectors: &CollectorPipeline,
    features: &Arc<FeatureExtractor>,
    model: &Arc<OnnxDetector>,
    risk_engine: &RiskEngine,
    store: &Arc<SecureStore>,
    uplink: Option<&UplinkClient>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
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

    if let Some(u) = uplink {
        let _ = u.report(detect_platform(), &events, &result);
    }

    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let config_path = std::env::var("DADM_CONFIG_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| std::path::PathBuf::from("config.json"));
    let config = AgentConfig::load(&config_path);

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

    let uplink: Option<UplinkClient> = if config.uplink.enabled {
        UplinkClient::new(config.uplink.clone())
    } else {
        None
    };

    let interval_secs = config.collectors.process_interval_secs;
    let run_daemon = interval_secs > 0;

    if run_daemon {
        info!(interval_secs, "daemon mode (Ctrl+C to stop)");
        static STOP: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
        let _ = ctrlc::set_handler(|| {
            STOP.store(true, std::sync::atomic::Ordering::Relaxed);
        });
        let mut cycle: u64 = 0;
        while !STOP.load(std::sync::atomic::Ordering::Relaxed) {
            cycle += 1;
            if let Err(e) = run_one_cycle(
                &collectors,
                &features,
                &model,
                &risk_engine,
                &store,
                uplink.as_ref(),
            ) {
                tracing::warn!(cycle, error = %e, "cycle failed");
            }
            for _ in 0..(interval_secs as u32) {
                if STOP.load(std::sync::atomic::Ordering::Relaxed) {
                    break;
                }
                std::thread::sleep(Duration::from_secs(1));
            }
        }
        info!("DADM agent stopping");
    } else {
        run_one_cycle(
            &collectors,
            &features,
            &model,
            &risk_engine,
            &store,
            uplink.as_ref(),
        )?;
        info!("DADM agent cycle complete");
    }

    Ok(())
}
