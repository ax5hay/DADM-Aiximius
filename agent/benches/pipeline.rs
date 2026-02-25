//! Pipeline benchmark: events → feature extraction (low-power device target).

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use dadm_agent::collectors::{CollectorPipeline, Event, EventKind, ProcessEvent};
use dadm_agent::config::CollectorsConfig;
use dadm_agent::features::FeatureExtractor;
use dadm_agent::config::FeaturesConfig;
use chrono::Utc;

fn make_dummy_events(n: usize) -> Vec<Event> {
    (0..n)
        .map(|i| {
            Event::new(
                EventKind::Process(ProcessEvent {
                    pid: i as u32,
                    ppid: Some(0),
                    name: format!("proc_{}", i),
                    exe: Some("/usr/bin/bench".to_string()),
                    cmdline: Some(format!("bench --id {}", i)),
                    uid: Some(1000),
                    started_at: Some(Utc::now().timestamp()),
                }),
                "bench",
            )
        })
        .collect()
}

fn bench_feature_extraction(c: &mut Criterion) {
    let config = FeaturesConfig {
        window_events: 100,
        feature_dim: 64,
    };
    let extractor = FeatureExtractor::new(config);
    let events = make_dummy_events(100);

    c.bench_function("feature_extract_100_events", |b| {
        b.iter(|| {
            let ev = black_box(events.clone());
            black_box(extractor.push(ev))
        })
    });
}

fn bench_collectors_snapshot(c: &mut Criterion) {
    let config = CollectorsConfig::default();
    let pipeline = CollectorPipeline::new(&config);

    c.bench_function("collectors_snapshot", |b| b.iter(|| black_box(pipeline.collect_snapshot())));
}

fn bench_full_pipeline(c: &mut Criterion) {
    let coll_config = CollectorsConfig::default();
    let feat_config = FeaturesConfig::default();
    let pipeline = CollectorPipeline::new(&coll_config);
    let extractor = FeatureExtractor::new(feat_config);

    c.bench_function("full_pipeline_snapshot_to_features", |b| {
        b.iter(|| {
            let events = pipeline.collect_snapshot();
            black_box(extractor.push(events))
        })
    });
}

criterion_group!(
    benches,
    bench_feature_extraction,
    bench_collectors_snapshot,
    bench_full_pipeline
);
criterion_main!(benches);
