from modules.web4_runtime.governance import AdaptiveGovernor, AlertManager, GovernanceMetrics


def test_adaptive_governor_low_volatility() -> None:
    governor = AdaptiveGovernor()

    for _ in range(100):
        governor.compute_adaptive_alpha(1000.0)

    metrics = governor.get_metrics()
    assert metrics.regulator_volatility < 0.2
    assert metrics.regulator_alpha_current >= 0.4


def test_adaptive_governor_high_volatility() -> None:
    governor = AdaptiveGovernor()

    for i in range(100):
        throughput = 500.0 if i % 2 == 0 else 1500.0
        governor.compute_adaptive_alpha(throughput)

    metrics = governor.get_metrics()
    assert metrics.regulator_volatility >= 0.5
    assert metrics.regulator_alpha_current <= 0.3


def test_alert_manager_thresholds() -> None:
    alert_manager = AlertManager()

    metrics = GovernanceMetrics(regulator_volatility=0.6)
    alerts = alert_manager.check_thresholds(metrics)
    assert len(alerts) == 1
    assert alerts[0]["level"] == "warning"

    metrics = GovernanceMetrics(regulator_volatility=0.9)
    alerts = alert_manager.check_thresholds(metrics)
    assert len(alerts) == 1
    assert alerts[0]["level"] == "critical"


def test_alert_manager_handler_callback() -> None:
    alert_manager = AlertManager()
    received_alerts: list[dict[str, float | str]] = []

    def handler(alerts: list[dict[str, float | str]]) -> None:
        received_alerts.extend(alerts)

    alert_manager.register_alert_handler(handler)

    metrics = GovernanceMetrics(regulator_volatility=0.9)
    alert_manager.check_thresholds(metrics)

    assert len(received_alerts) == 1
    assert received_alerts[0]["level"] == "critical"
