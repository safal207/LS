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
