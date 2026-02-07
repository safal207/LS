from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple


@dataclass
class _HookHandle:
    remove: Callable[[], None]


class LLMHooks:
    def __init__(self, model: Any) -> None:
        self.model = model
        self._handles: List[_HookHandle] = []
        self.signals: Dict[str, Any] = {
            "attentions": [],
            "hidden_states": [],
            "logits": [],
            "context_length": None,
        }

    def attach(self) -> None:
        def attn_hook(_module: Any, _input: Tuple[Any, ...], output: Any) -> None:
            self.signals["attentions"].append(_detach_tensor(output))

        def hidden_hook(_module: Any, _input: Tuple[Any, ...], output: Any) -> None:
            self.signals["hidden_states"].append(_detach_tensor(output))

        def logits_hook(_module: Any, inputs: Tuple[Any, ...], output: Any) -> None:
            self.signals["logits"].append(_detach_tensor(output))
            context_length = _infer_context_length(inputs)
            if context_length is not None:
                self.signals["context_length"] = context_length

        named_modules = getattr(self.model, "named_modules", None)
        if callable(named_modules):
            for name, module in named_modules():
                lowered = name.lower()
                if "attn" in lowered:
                    self._handles.append(_register_hook(module, attn_hook))
                if "mlp" in lowered or "ffn" in lowered:
                    self._handles.append(_register_hook(module, hidden_hook))

        self._handles.append(_register_hook(self.model, logits_hook))

    def detach(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()


class STTHooks:
    def __init__(self) -> None:
        self.signals: Dict[str, Any] = {}
        self._original_transcribe: Callable[..., Any] | None = None

    def wrap_transcribe(self, model: Any) -> Any:
        original = model.transcribe
        self._original_transcribe = original

        def wrapped(*args: Any, **kwargs: Any):
            import time

            start = time.perf_counter()
            segments, info = original(*args, **kwargs)
            elapsed = time.perf_counter() - start
            segment_list = list(segments)
            self.signals["segments_count"] = len(segment_list)
            self.signals["transcription_time"] = elapsed
            self.signals["language"] = getattr(info, "language", None)
            self.signals["audio_seconds"] = _infer_audio_seconds(args, kwargs)
            return segment_list, info

        model.transcribe = wrapped
        return model

    def restore(self, model: Any) -> None:
        if self._original_transcribe is not None:
            model.transcribe = self._original_transcribe
            self._original_transcribe = None


def _register_hook(module: Any, hook: Callable[..., Any]) -> _HookHandle:
    register = getattr(module, "register_forward_hook", None)
    if not callable(register):
        return _HookHandle(remove=lambda: None)
    handle = register(hook)
    remove = getattr(handle, "remove", None)
    if callable(remove):
        return _HookHandle(remove=remove)
    return _HookHandle(remove=lambda: None)


def _detach_tensor(value: Any) -> Any:
    if hasattr(value, "detach"):
        return value.detach().cpu()
    if isinstance(value, (list, tuple)) and value:
        return _detach_tensor(value[0])
    return value


def _infer_context_length(inputs: Tuple[Any, ...]) -> int | None:
    if not inputs:
        return None
    first = inputs[0]
    if hasattr(first, "shape"):
        shape = getattr(first, "shape", None)
        if shape and len(shape) >= 2:
            return int(shape[-1])
    if isinstance(first, dict) and "input_ids" in first:
        input_ids = first["input_ids"]
        if hasattr(input_ids, "shape"):
            shape = getattr(input_ids, "shape", None)
            if shape and len(shape) >= 2:
                return int(shape[-1])
    return None


def _infer_audio_seconds(args: Tuple[Any, ...], _kwargs: Dict[str, Any]) -> float | None:
    if not args:
        return None
    source = args[0]
    if isinstance(source, str) and source.lower().endswith(".wav"):
        import wave

        with wave.open(source, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
        return frames / float(rate)
    return None
