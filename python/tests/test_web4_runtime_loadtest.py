from modules.web4_runtime.loadtest import LoadTestConfig, run_load_test


def test_phase1_load_harness_both_modes() -> None:
    report = run_load_test(
        LoadTestConfig(
            phase="phase1",
            mode="both",
            sessions=2,
            messages_per_session=10,
            max_queue=8,
            total_limit=16,
            per_session_limit=8,
            block_timeout_s=0.8,
            random_seed=7,
        )
    )

    assert report["phase"] == "phase1"
    assert report["mode"] == "both"
    assert report["overall_passed"] is True
    assert len(report["results"]) == 2
    for result in report["results"]:
        assert result["errors"] == []
        assert result["max_total_pending"] <= result["total_limit"]


def test_phase2_load_harness_sync_mode() -> None:
    config = LoadTestConfig(
        phase="phase2",
        mode="sync",
        sessions=4,
        messages_per_session=30,
        max_queue=16,
        total_limit=64,
        per_session_limit=16,
        random_seed=11,
    )
    report = run_load_test(config)

    assert report["phase"] == "phase2"
    assert report["mode"] == "sync"
    assert report["overall_passed"] is True
    assert len(report["results"]) == 1

    result = report["results"][0]
    assert result["scenario"] == "phase2_stress_sanity"
    assert result["attempted"] == config.sessions * config.messages_per_session
    assert result["max_total_pending"] <= config.total_limit
    assert result["errors"] == []


def test_phase3_load_harness_sync_mode() -> None:
    config = LoadTestConfig(
        phase="phase3",
        mode="sync",
        sessions=3,
        messages_per_session=12,
        max_queue=12,
        total_limit=36,
        per_session_limit=12,
        random_seed=13,
        chaos_disconnect_rate=0.2,
        burst_probability=0.15,
        burst_size=4,
        gc_pressure=True,
    )
    report = run_load_test(config)

    assert report["overall_passed"] is True
    result = report["results"][0]
    assert result["scenario"] == "phase3_chaos_validation"
    assert result["max_total_pending"] <= config.total_limit
    assert result["errors"] == []
    assert "disconnect_events" in result["extra"]


def test_phase4_load_harness_async_mode() -> None:
    config = LoadTestConfig(
        phase="phase4",
        mode="async",
        sessions=2,
        messages_per_session=8,
        max_queue=10,
        total_limit=20,
        per_session_limit=10,
        random_seed=5,
        soak_duration_s=0.15,
        target_messages_per_s=120,
        burst_probability=0.1,
        burst_size=3,
        chaos_disconnect_rate=0.1,
    )
    report = run_load_test(config)

    assert report["overall_passed"] is True
    result = report["results"][0]
    assert result["scenario"] == "phase4_soak_stability"
    assert result["mode"] == "async"
    assert result["max_total_pending"] <= config.total_limit
    assert result["errors"] == []
    assert result["extra"]["loop_steps"] > 0
