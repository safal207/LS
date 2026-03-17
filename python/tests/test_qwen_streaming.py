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


class _FakeSession:
    def __init__(self, lines=None):
        self._lines = lines or []
        self.headers = {}

    def post(self, *args, **kwargs):
        assert kwargs.get("stream") is True
        return _FakeStreamResponse(self._lines)


class _FakeRequests:
    def __init__(self, lines=None):
        self._lines = lines or []

    def Session(self):
        return _FakeSession(self._lines)


def test_build_ollama_payload_uses_env_num_predict(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_PREDICT", "64")
    monkeypatch.setattr(qwen_handler, "requests", _FakeRequests())
    handler = qwen_handler.QwenHandler(use_cloud_api=False)

    _, payload = handler._build_ollama_payload("hello", messages=None, stream=False)
    assert payload["options"]["num_predict"] == 64


def test_generate_with_ollama_stream_emits_tokens_and_returns_text(monkeypatch):
    frames = [
        json.dumps({"response": "Привет"}),
        json.dumps({"response": ", мир"}),
    ]
    monkeypatch.setattr(qwen_handler, "requests", _FakeRequests(frames))
    handler = qwen_handler.QwenHandler(use_cloud_api=False)

    chunks = []
    result = handler.generate_with_ollama_stream("test", on_token=chunks.append)

    assert chunks == ["Привет", ", мир"]
    assert result == "Привет, мир"
