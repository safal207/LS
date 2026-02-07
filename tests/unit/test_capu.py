from __future__ import annotations

import importlib.util
import wave

from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.store import MemoryRecord
from codex.capu import Tracer
from codex.capu.features import extract_llm_features, extract_stt_features


class DummyHandle:
    def __init__(self) -> None:
        self.removed = False

    def remove(self) -> None:
        self.removed = True


class DummyLLM:
    def __init__(self) -> None:
        self.hooks = []

    def register_forward_hook(self, hook):
        self.hooks.append(hook)
        return DummyHandle()

    def named_modules(self):
        return []


class DummySTT:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(self, _source, **_kwargs):
        self.calls += 1
        segments = ["seg1", "seg2"]
        info = type("Info", (), {"language": "en"})()
        return iter(segments), info


def _write_wav(path):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)


def test_tracer_llm_roundtrip():
    tracer = Tracer()
    model = DummyLLM()
    tracer.start_llm_session("demo", model)
    signals = tracer.end_llm_session("demo")
    assert "attentions" in signals
    assert signals["attentions"] == []


def test_tracer_stt_roundtrip(tmp_path):
    tracer = Tracer()
    model = DummySTT()
    _, wrapped = tracer.start_stt_session("stt-demo", model)
    sample = tmp_path / "sample.wav"
    _write_wav(sample)
    segments, info = wrapped.transcribe(str(sample), beam_size=1)
    assert list(segments) == ["seg1", "seg2"]
    assert info.language == "en"
    signals = tracer.end_stt_session("stt-demo")
    assert signals["segments_count"] == 2
    assert signals["audio_seconds"] == 1.0


def test_extract_stt_features():
    features = extract_stt_features(
        {
            "segments_count": 4,
            "transcription_time": 2.0,
            "audio_seconds": 4.0,
        }
    )
    assert features["segments_count"] == 4.0
    assert features["rtf_estimate"] == 0.5


def test_extract_llm_features_empty():
    assert extract_llm_features({}) == {}


def test_extract_llm_features_with_torch():
    if importlib.util.find_spec("torch") is None:
        return
    import torch

    logits = torch.tensor([[0.0, 1.0]])
    attn = torch.zeros((1, 1, 2, 2))
    attn[..., 0, 0] = 1.0
    features = extract_llm_features({"attentions": [attn], "logits": [logits], "context_length": 2})
    assert features["context_length"] == 2.0
    assert "avg_attention_entropy" in features
    assert "logits_confidence_margin" in features


def test_causal_graph_conditions_from_capu_metrics():
    record = MemoryRecord.build(
        model="demo",
        model_type="llm",
        metrics={
            "logits_confidence_margin": 0.05,
            "avg_attention_entropy": 6.0,
            "segments_count": 30,
        },
        hardware={},
    )
    conditions = list(CausalGraph._conditions_from_record(record))
    assert "low_confidence_logits" in conditions
    assert "diffuse_attention" in conditions
    assert "stt_segments>25" in conditions
