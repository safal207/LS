import pytest
from codex.benchmark.report import BenchmarkResult, BenchmarkReport, model_report

def test_benchmark_result_to_from_dict():
    metrics = {"tokenspersecond": 10.5, "peakrammb": 512.0}
    metadata = {"device": "cpu"}
    result = BenchmarkResult(
        model="test-model",
        model_type="llm",
        metrics=metrics,
        success=True,
        metadata=metadata,
        timestamp="2023-01-01T00:00:00Z"
    )

    payload = result.to_dict()
    assert payload["model"] == "test-model"
    assert payload["type"] == "llm"
    assert payload["metrics"] == metrics
    assert payload["success"] is True
    assert payload["metadata"] == metadata
    assert payload["timestamp"] == "2023-01-01T00:00:00Z"

    restored = BenchmarkResult.from_dict(payload)
    assert restored == result

def test_benchmark_report_save_load(tmp_path):
    report = BenchmarkReport(tmp_path)
    result = BenchmarkResult(
        model="m1",
        model_type="llm",
        metrics={"m": 1.0}
    )

    saved_path = report.save(result)
    assert saved_path.exists()
    assert saved_path.name == "m1.json"

    loaded = report.load("m1")
    assert loaded.model == "m1"
    assert loaded.metrics == {"m": 1.0}

def test_benchmark_report_list_load_all(tmp_path):
    report = BenchmarkReport(tmp_path)
    r1 = BenchmarkResult(model="m1", model_type="llm", metrics={"v": 1.0})
    r2 = BenchmarkResult(model="m2", model_type="stt", metrics={"v": 2.0})

    report.save(r1)
    report.save(r2)

    models = report.list_models()
    assert models == ["m1", "m2"]

    all_results = report.load_all()
    assert len(all_results) == 2
    assert all_results[0].model == "m1"
    assert all_results[1].model == "m2"

def test_benchmark_report_compare(tmp_path):
    report = BenchmarkReport(tmp_path)
    r1 = BenchmarkResult(model="slow", model_type="llm", metrics={"loadtimems": 100.0})
    r2 = BenchmarkResult(model="fast", model_type="llm", metrics={"loadtimems": 50.0})
    r3 = BenchmarkResult(model="failed", model_type="llm", metrics={"loadtimems": 10.0}, success=False)

    results = [r1, r2, r3]

    # loadtimems: LOWER_IS_BETTER = True. sorted ascending.
    compared = report.compare("loadtimems", results)
    assert len(compared) == 2
    assert compared[0]["model"] == "fast"
    assert compared[1]["model"] == "slow"

    # tokenspersecond: not in LOWER_IS_BETTER. sorted descending.
    r4 = BenchmarkResult(model="m4", model_type="llm", metrics={"tokenspersecond": 5.0})
    r5 = BenchmarkResult(model="m5", model_type="llm", metrics={"tokenspersecond": 15.0})
    compared_desc = report.compare("tokenspersecond", [r4, r5])
    assert compared_desc[0]["model"] == "m5"
    assert compared_desc[1]["model"] == "m4"

def test_benchmark_report_model_report_dict(tmp_path):
    report = BenchmarkReport(tmp_path)
    r1 = BenchmarkResult(model="m1", model_type="llm", metrics={"tokenspersecond": 10.0, "loadtimems": 100.0})
    r2 = BenchmarkResult(model="m2", model_type="llm", metrics={"tokenspersecond": 20.0, "loadtimems": 50.0})

    report.save(r1)
    report.save(r2)

    rep_dict = report.model_report("m1")
    assert rep_dict["result"]["model"] == "m1"
    assert "tokenspersecond" in rep_dict["comparisons"]
    assert rep_dict["comparisons"]["tokenspersecond"][0]["model"] == "m2" # m2 has 20.0 (higher)
    assert rep_dict["comparisons"]["loadtimems"][0]["model"] == "m2" # m2 has 50.0 (lower)

def test_standalone_model_report_markdown():
    metrics = {
        "result": {
            "model": "test-model",
            "type": "llm",
            "timestamp": "2023-01-01",
            "metrics": {"m1": 1.0, "m2": 2.0}
        },
        "comparisons": {
            "m1": [
                {"model": "test-model", "value": 1.0},
                {"model": "other", "value": 0.5}
            ]
        }
    }

    md = model_report(metrics)
    assert "# Benchmark Report" in md
    assert "## Model: test-model" in md
    assert "- **Type**: llm" in md
    assert "### Metrics" in md
    assert "- **m1**: 1.0" in md
    assert "- **m2**: 2.0" in md
    assert "### Comparisons" in md
    assert "#### m1" in md
    assert "| **test-model** | 1.0 |" in md
    assert "| other | 0.5 |" in md

def test_standalone_model_report_empty():
    md = model_report({})
    assert "# Benchmark Report" in md
    assert "## Model: Unknown" in md
    assert "No metrics available." in md
