from agent.tool_runtime import ToolRuntime


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
    assert state["tool_health"]["answer_with_tool"]["is_healthy"] is False
    assert state["tool_health"]["answer_with_tool"]["error_count"] == 1
    assert state["tool_audit_log"][-1]["status"] == "blocked"


def test_tool_runtime_opens_circuit_after_repeated_failures() -> None:
    state = {}

    def broken_tool(payload: dict) -> dict:
        raise RuntimeError("tool down")

    runtime = ToolRuntime(
        state,
        tool_registry={"answer_with_tool": broken_tool},
        sandbox_mode=True,
        circuit_breaker_threshold=2,
        max_retries=0,
    )

    first = runtime.execute("answer_with_tool", {"event_sequence": []})
    second = runtime.execute("answer_with_tool", {"event_sequence": []})
    third = runtime.execute("answer_with_tool", {"event_sequence": []})

    assert first["status"] == "error"
    assert second["status"] == "error"
    assert second["circuit_open"] is True
    assert third["status"] == "blocked"
    assert third["reason"] == "circuit_open"
    assert state["tool_health"]["answer_with_tool"]["circuit_open"] is True


def test_tool_runtime_times_out_before_blocking_pipeline() -> None:
    import time

    state = {}

    def slow_tool(payload: dict) -> dict:
        time.sleep(0.15)
        return {"ok": True}

    runtime = ToolRuntime(
        state,
        tool_registry={"answer_with_tool": slow_tool},
        sandbox_mode=True,
        default_timeout_s=0.02,
        max_retries=0,
    )

    result = runtime.execute("answer_with_tool", {"event_sequence": []})

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
