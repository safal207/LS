from codex.benchmark.report import BenchmarkReport, BenchmarkResult
from codex.cognitive.self_model.integration import UnifiedCognitiveLoop
from codex.hardware.profiler import GPUInfo, HardwareProfile, TorchInfo
from codex.lpi import PresenceMonitor
from codex.registry.model_registry import ModelRegistry
from codex.selector.model_selector import AdaptiveModelSelector


class StaticProfiler:
    def __init__(self, profile: HardwareProfile) -> None:
        self._profile = profile

    def collect(self) -> HardwareProfile:
        return self._profile


def build_selector(tmp_path) -> AdaptiveModelSelector:
    registry = ModelRegistry()
    registry.register(
        "fast-model",
        {
            "type": "llm",
            "path": "models/fast",
            "ram_required": "2GB",
            "device": "cpu",
        },
    )
    registry.register(
        "quality-model",
        {
            "type": "llm",
            "path": "models/quality",
            "ram_required": "2GB",
            "device": "cpu",
        },
    )
    profile = HardwareProfile(
        cpu_cores=8,
        cpu_freq_ghz=3.2,
        cpu_arch="x86_64",
        ram_total_mb=16384,
        ram_available_mb=12000,
        ram_used_mb=4000,
        gpu=GPUInfo(name=None, vram_total_mb=None, vram_free_mb=None, cuda=False, cuda_version=None),
        torch=TorchInfo(cuda=False, mps=False, fp16=False, bf16=False),
        libraries={},
    )
    profiler = StaticProfiler(profile)

    report = BenchmarkReport(tmp_path)
    report.save(
        BenchmarkResult(
            model="fast-model",
            model_type="llm",
            metrics={
                "firsttokenlatency_ms": 10.0,
                "tokenspersecond": 180.0,
                "loadtimems": 120.0,
                "peakrammb": 5000.0,
                "peakvrammb": 0.0,
                "stability_score": 0.35,
            },
        )
    )
    report.save(
        BenchmarkResult(
            model="quality-model",
            model_type="llm",
            metrics={
                "firsttokenlatency_ms": 55.0,
                "tokenspersecond": 260.0,
                "loadtimems": 240.0,
                "peakrammb": 1500.0,
                "peakvrammb": 0.0,
                "stability_score": 0.9,
            },
        )
    )

    return AdaptiveModelSelector(registry, profiler, benchmark_report=report)


def test_self_model_affective_meta_selector_integration(tmp_path):
    selector = build_selector(tmp_path)
    monitor = PresenceMonitor()
    monitor.update(capu_features={"rtf_estimate": 1.5}, metrics={}, hardware={})

    loop = UnifiedCognitiveLoop(selector=selector, presence_monitor=monitor)

    first = loop.run_task(
        {"task": "realtime_interview"},
        capu_features={"avg_attention_entropy": 6.1},
    )
    assert first["strategy"] == "balanced"
    assert loop.self_model.load > 0.0
    assert loop.self_model.fragmentation > 0.0
    assert loop.affective_layer.energy < 1.0
    assert first["selection"].selected_model == "fast-model"

    for _ in range(3):
        loop.self_model.update_from_state("fragmented")

    second = loop.run_task(
        {"task": "realtime_interview"},
        capu_features={"avg_attention_entropy": 6.1},
    )
    assert second["strategy"] == "stability_first"
    assert second["selection"].selected_model == "quality-model"
