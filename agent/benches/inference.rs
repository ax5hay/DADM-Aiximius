//! Inference benchmark: feature vector → ONNX predict (low-power device target).

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use dadm_agent::features::FeatureVector;
use dadm_agent::model::OnnxDetector;
use std::path::Path;

fn bench_inference_no_model(c: &mut Criterion) {
    let dim = 64;
    let detector = OnnxDetector::load(Path::new("nonexistent.onnx"), dim).unwrap();
    let fv = FeatureVector {
        dim,
        values: vec![0.1f32; dim],
        event_id: "bench".to_string(),
        ts: 0,
    };

    c.bench_function("inference_no_model_64d", |b| {
        b.iter(|| detector.predict(black_box(&fv)))
    });
}

fn bench_inference_feature_dim(c: &mut Criterion) {
    let dim = 64;
    let detector = OnnxDetector::load(Path::new("nonexistent.onnx"), dim).unwrap();
    let fv = FeatureVector {
        dim,
        values: vec![0.1f32; dim],
        event_id: "bench".to_string(),
        ts: 0,
    };

    let mut g = c.benchmark_group("inference_by_dim");
    for d in [16, 32, 64, 128] {
        let fv = FeatureVector {
            dim: d,
            values: vec![0.1f32; d],
            event_id: "bench".to_string(),
            ts: 0,
        };
        g.bench_function(format!("dim_{}", d).as_str(), |b| {
            b.iter(|| detector.predict(black_box(&fv)))
        });
    }
    g.finish();
}

criterion_group!(benches, bench_inference_no_model, bench_inference_feature_dim);
criterion_main!(benches);
