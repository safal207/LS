import json

from modules.llm import qwen_handler


class _FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line


class _FakeJsonResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, lines=None, payload=None):
        self._lines = lines or []
        self._payload = payload or {"response": "ok"}
        self.headers = {}

    def post(self, *args, **kwargs):
        if kwargs.get("stream") is True:
            return _FakeStreamResponse(self._lines)
        return _FakeJsonResponse(self._payload)


class _FakeRequests:
    def __init__(self, lines=None, payload=None):
        self._lines = lines or []
        self._payload = payload or {"response": "ok"}

    def Session(self):
        return _FakeSession(self._lines, self._payload)


def test_build_ollama_payload_uses_env_num_predict(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_PREDICT", "64")
    monkeypatch.setattr(qwen_handler, "requests", _FakeRequests())
    handler = qwen_handler.QwenHandler(use_cloud_api=False)

    _, payload = handler._build_ollama_payload("hello", messages=None, stream=False)
    assert payload["options"]["num_predict"] == 64


def test_generate_with_ollama_stream_emits_tokens_and_returns_text(monkeypatch):
    monkeypatch.setattr(qwen_handler, "_extract_ollama_token_cpp", lambda frame, has_messages: None)
    frames = [
        json.dumps({"response": "Привет"}),
        json.dumps({"response": ", мир"}),
    ]
    monkeypatch.setattr(qwen_handler, "requests", _FakeRequests(lines=frames))
    handler = qwen_handler.QwenHandler(use_cloud_api=False)

    chunks = []
    result = handler.generate_with_ollama_stream("test", on_token=chunks.append)

    assert chunks == ["Привет", ", мир"]
    assert result == "Привет, мир"


def test_generate_response_non_streaming_path_still_works(monkeypatch):
    monkeypatch.setattr(qwen_handler, "requests", _FakeRequests(payload={"response": "final text"}))
    handler = qwen_handler.QwenHandler(use_cloud_api=False)

    result = handler.generate_response("prompt", stream=False)
    assert result == "final text"


def test_generate_response_streaming_path_uses_callback(monkeypatch):
    monkeypatch.setattr(qwen_handler, "_extract_ollama_token_cpp", lambda frame, has_messages: None)
    frames = [json.dumps({"response": "A"}), json.dumps({"response": "B"})]
    monkeypatch.setattr(qwen_handler, "requests", _FakeRequests(lines=frames))
    handler = qwen_handler.QwenHandler(use_cloud_api=False)

    seen = []
    result = handler.generate_response("prompt", stream=True, on_token=seen.append)

    assert seen == ["A", "B"]
    assert result == "AB"


def test_extract_stream_token_uses_rust_fast_path(monkeypatch):
    class _Rust:
        @staticmethod
        def extract_ollama_token(frame_line, has_messages):
            assert has_messages is False
            return "R"

    monkeypatch.setattr(qwen_handler, "_ghostgpt_core", _Rust())
    token = qwen_handler._extract_stream_token('{"response":"x"}', False)
    assert token == "R"


def test_extract_stream_token_falls_back_to_python_when_rust_errors(monkeypatch):
    class _Rust:
        @staticmethod
        def extract_ollama_token(frame_line, has_messages):
            raise RuntimeError("bridge fail")

    monkeypatch.setattr(qwen_handler, "_ghostgpt_core", _Rust())
    token = qwen_handler._extract_stream_token('{"response":"fallback"}', False)
    assert token == "fallback"


def test_extract_stream_token_uses_cpp_when_rust_unavailable(monkeypatch):
    monkeypatch.setattr(qwen_handler, "_ghostgpt_core", None)
    monkeypatch.setattr(qwen_handler, "_extract_ollama_token_cpp", lambda frame, has_messages: "C")
    assert qwen_handler._extract_stream_token('{"response":"x"}', False) == "C"


def test_extract_stream_token_falls_back_to_python_when_cpp_missing(monkeypatch):
    monkeypatch.setattr(qwen_handler, "_ghostgpt_core", None)
    monkeypatch.setattr(qwen_handler, "_extract_ollama_token_cpp", lambda frame, has_messages: None)
    assert qwen_handler._extract_stream_token('{"response":"py"}', False) == "py"
