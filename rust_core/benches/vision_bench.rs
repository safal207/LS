use criterion::{criterion_group, criterion_main, Criterion};
use ghostgpt_core::vision_core::RustSceneChangeDetector;

fn bench_scene_change(c: &mut Criterion) {
    let mut detector = RustSceneChangeDetector::new();
    let frame_a = vec![0u8; 1920 * 1080 * 3];
    let frame_b = vec![255u8; 1920 * 1080 * 3];

    c.bench_function("scene_change_1080p", |b| {
        b.iter(|| {
            let _ =
                detector.calculate_scene_score(frame_a.clone(), 1920, 1080, Some(String::new()));
            let _ = detector.calculate_scene_score(
                frame_b.clone(),
                1920,
                1080,
                Some(String::from("diff")),
            );
        })
    });
}

criterion_group!(benches, bench_scene_change);
criterion_main!(benches);
