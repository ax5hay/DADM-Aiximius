//! Secure storage benchmark: insert and read encrypted events.

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use dadm_agent::storage::SecureStore;
use tempfile::tempdir;

fn bench_insert_event(c: &mut Criterion) {
    let dir = tempdir().unwrap();
    let path = dir.path().join("store.db");
    let store = SecureStore::open(&path, b"bench-secret").unwrap();
    let payload = r#"{"id":"ev-1","ts":0,"kind":"process","source":"bench"}"#;

    c.bench_function("storage_insert_event", |b| {
        b.iter(|| {
            let id = format!("ev-{}", black_box(0));
            black_box(store.insert_event(&id, 0, "process", payload, Some(0.5))).unwrap()
        })
    });
}

fn bench_insert_and_read(c: &mut Criterion) {
    let dir = tempdir().unwrap();
    let path = dir.path().join("store.db");
    let store = SecureStore::open(&path, b"bench-secret").unwrap();
    let payload = r#"{"id":"ev-1","ts":0,"kind":"process","source":"bench"}"#;
    store.insert_event("ev-1", 0, "process", payload, Some(0.5)).unwrap();

    c.bench_function("storage_get_event", |b| {
        b.iter(|| black_box(store.get_event("ev-1")).unwrap())
    });
}

criterion_group!(benches, bench_insert_event, bench_insert_and_read);
criterion_main!(benches);
