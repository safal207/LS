use criterion::{black_box, criterion_group, criterion_main, BatchSize, Criterion};
use ghostgpt_core::vision_core::RustSceneChangeDetector;

fn bench_scene_change(c: &mut Criterion) {
    let mut detector = RustSceneChangeDetector::new();
    let frame_a = vec![0u8; 1920 * 1080 * 3];
    let frame_b = vec![255u8; 1920 * 1080 * 3];

    // Includes clone cost (~6 MB memcpy) to reflect real ownership transfer.
    c.bench_function("scene_change_1080p", |b| {
        b.iter(|| {
            let _ = detector.calculate_scene_score(
                black_box(frame_a.clone()),
                1920,
                1080,
                Some(String::new()),
            );
            let _ = detector.calculate_scene_score(
                black_box(frame_b.clone()),
                1920,
                1080,
                Some(String::from("diff")),
            );
        })
    });

    // Isolates pure compute from allocation.
    c.bench_function("scene_change_1080p_compute_only", |b| {
        let mut det = RustSceneChangeDetector::new();
        b.iter_batched(
            || (frame_a.clone(), frame_b.clone()),
            |(fa, fb)| {
                let _ = det.calculate_scene_score(black_box(fa), 1920, 1080, Some(String::new()));
                let _ = det.calculate_scene_score(
                    black_box(fb),
                    1920,
                    1080,
                    Some(String::from("diff")),
                );
            },
            BatchSize::LargeInput,
        )
    });
}

criterion_group!(benches, bench_scene_change);
criterion_main!(benches);
