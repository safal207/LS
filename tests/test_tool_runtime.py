from agent.tool_runtime import ToolRuntime


class _TestAdapter:
    def __init__(self, healthy: bool = True):
        self._healthy = healthy

    def name(self) -> str:
        return "retrieve_context"

    def healthcheck(self) -> bool:
        return self._healthy

    def execute(self, payload: dict) -> dict:
        return {"ok": True, "payload_size": len(payload)}


def test_tool_runtime_executes_registered_tool_and_updates_audit() -> None:
    state = {}

    def tool(payload: dict) -> dict:
        return {"ok": True, "size": len(payload.get("event_sequence", []))}

    runtime = ToolRuntime(state, tool_registry={"answer_with_tool": tool}, sandbox_mode=True)
    result = runtime.execute("answer_with_tool", {"event_sequence": [{"type": "decision"}]})

    assert result["status"] == "ok"
    assert result["result"]["ok"] is True
    assert state["tool_health"]["answer_with_tool"]["is_healthy"] is True
    assert state["tool_health"]["answer_with_tool"]["error_count"] == 0
    assert state["tool_audit_log"][-1]["status"] == "ok"


def test_tool_runtime_blocks_invalid_payload_in_sandbox() -> None:
    state = {}

    def tool(payload: dict) -> dict:
        return {"ok": True, "payload": payload}

    runtime = ToolRuntime(state, tool_registry={"answer_with_tool": tool}, sandbox_mode=True)
    result = runtime.execute("answer_with_tool", {"command": "rm -rf /"})

    assert result["status"] == "blocked"
    assert "tool_health" not in state or "answer_with_tool" not in state.get("tool_health", {})
    assert state["tool_audit_log"][-1]["status"] == "blocked"


def test_tool_runtime_executes_adapter_registry_tool() -> None:
    state = {}
    runtime = ToolRuntime(state, tool_adapters={"retrieve_context": _TestAdapter(healthy=True)})

    result = runtime.execute("retrieve_context", {"event_sequence": [{"type": "decision"}]})

    assert result["status"] == "ok"
    assert result["action"] == "retrieve_context"


def test_tool_runtime_active_healthcheck_and_degradation() -> None:
    state = {}
    runtime = ToolRuntime(state, tool_adapters={"retrieve_context": _TestAdapter(healthy=False)})

    health = runtime.run_healthchecks(active=True)
    result = runtime.execute("retrieve_context", {"event_sequence": []})

    assert health["retrieve_context"] is False
    assert result["status"] == "circuit_open"
    assert result["reason"] == "tool_unhealthy_degraded"


def test_tool_runtime_passive_healthcheck_returns_cached_state() -> None:
    state = {"tool_health": {"retrieve_context": {"is_healthy": True}}}
    runtime = ToolRuntime(state, tool_adapters={"retrieve_context": _TestAdapter(healthy=False)})

    health = runtime.run_healthchecks(active=False)

    assert health == {"retrieve_context": True}


def test_tool_runtime_audit_log_retention() -> None:
    state = {}

    def tool(payload: dict) -> dict:
        return {"ok": True}

    runtime = ToolRuntime(state, tool_registry={"answer_with_tool": tool}, audit_log_retention=2)
    runtime.execute("answer_with_tool", {"event_sequence": []})
    runtime.execute("answer_with_tool", {"event_sequence": []})
    runtime.execute("answer_with_tool", {"event_sequence": []})

    assert result["status"] == "timeout"
    assert "timed out" in result["error"]
    assert state["tool_health"]["answer_with_tool"]["is_healthy"] is False


def test_tool_runtime_supports_tool_adapter_registration() -> None:
    from agent.tool_runtime import InMemoryDataToolAdapter

    state = {}
    adapter = InMemoryDataToolAdapter("data_lookup", state)
    runtime = ToolRuntime(state, tool_adapters={"data_lookup": adapter}, sandbox_mode=True)

    set_result = runtime.execute("data_lookup", {"op": "set", "key": "alpha", "value": 7})
    get_result = runtime.execute("data_lookup", {"op": "get", "key": "alpha"})

    assert set_result["status"] == "ok"
    assert get_result["result"]["value"] == 7


def test_tool_runtime_active_healthchecks_persist_snapshot() -> None:
    from agent.tool_runtime import InMemoryDataToolAdapter

    state = {}
    runtime = ToolRuntime(
        state,
        tool_adapters={"data_lookup": InMemoryDataToolAdapter("data_lookup", state)},
        sandbox_mode=True,
    )

    report = runtime.run_active_healthchecks()

    assert report["data_lookup"]["ok"] is True
    assert "last_tool_healthcheck" in state
    assert state["tool_health"]["data_lookup"]["is_healthy"] is True
