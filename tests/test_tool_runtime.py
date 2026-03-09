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
