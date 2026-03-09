from agent.health_scheduler import ToolHealthcheckScheduler
from agent.tool_runtime import ToolRuntime


class _Adapter:
    def __init__(self, healthy: bool):
        self.healthy = healthy

    def name(self) -> str:
        return "retrieve_context"

    def healthcheck(self) -> bool:
        return self.healthy

    def execute(self, payload: dict) -> dict:
        return {"ok": True}


def test_health_scheduler_persists_history() -> None:
    state = {}
    runtime = ToolRuntime(state, tool_adapters={"retrieve_context": _Adapter(True)})
    scheduler = ToolHealthcheckScheduler(runtime, interval_s=15.0)

    result = scheduler.run_once(active=True)

    assert result["mode"] == "active"
    assert result["interval_s"] == 15.0
    assert state["last_tool_healthcheck"]["mode"] == "active"
    assert len(state["tool_healthcheck_history"]) == 1


def test_health_scheduler_run_periodic_and_retention() -> None:
    state = {}
    runtime = ToolRuntime(state, tool_adapters={"retrieve_context": _Adapter(True)})
    scheduler = ToolHealthcheckScheduler(runtime, interval_s=1.0, history_retention=2)

    results = scheduler.run_periodic(cycles=3, active=True)

    assert len(results) == 3
    assert len(state["tool_healthcheck_history"]) == 2
