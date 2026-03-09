from agent.tool_adapters import DataAdapter, HTTPContextAdapter
from agent.tool_runtime import ToolRuntime


def test_http_context_adapter_execute_via_runtime() -> None:
    state = {}

    def fake_http_client(**kwargs):
        assert kwargs["path"] == "/context"
        return {"ok": True, "context": "hello"}

    adapter = HTTPContextAdapter(base_url="http://example.local", http_client=fake_http_client)
    runtime = ToolRuntime(state, tool_adapters={"retrieve_context": adapter})

    result = runtime.execute("retrieve_context", {"query": "hi"})

    assert result["status"] == "ok"
    assert result["result"]["context"] == "hello"


def test_http_context_adapter_healthcheck_false_on_error() -> None:
    def fake_http_client(**kwargs):
        raise RuntimeError("boom")

    adapter = HTTPContextAdapter(base_url="http://example.local", http_client=fake_http_client)

    assert adapter.healthcheck() is False


def test_data_adapter_roundtrip_operations() -> None:
    adapter = DataAdapter()

    set_result = adapter.execute({"operation": "set", "key": "k", "value": 7})
    get_result = adapter.execute({"operation": "get", "key": "k"})
    list_result = adapter.execute({"operation": "list"})
    delete_result = adapter.execute({"operation": "delete", "key": "k"})

    assert set_result["ok"] is True
    assert get_result["value"] == 7
    assert "k" in list_result["keys"]
    assert delete_result["existed"] is True
