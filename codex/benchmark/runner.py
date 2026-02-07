from __future__ import annotations

import importlib.util
import math
import time
import wave
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, List

import psutil

from codex.causal_memory import CausalMemoryLayer
from codex.registry import ModelRegistry

from .metrics import LLMMetrics, STTMetrics, VADMetrics, stability_score
from .report import BenchmarkReport, BenchmarkResult

DEFAULT_PROMPT = "Explain what a neural network is in one paragraph."


class BenchmarkRunner:
    def __init__(
        self,
        registry: ModelRegistry,
        results_dir: str | Path | None = None,
        stability_runs: int = 3,
        memory_layer: CausalMemoryLayer | None = None,
    ) -> None:
        self.registry = registry
        self.results_dir = Path(results_dir or "benchmark_results")
        self.reporter = BenchmarkReport(self.results_dir)
        self.stability_runs = max(1, stability_runs)
        self.assets_dir = Path(__file__).resolve().parent / "assets"
        self.sample_wav = self.assets_dir / "sample_5s.wav"
        self.memory_layer = memory_layer

    def run(self, model_name: str, save: bool = True, raise_on_error: bool = True) -> BenchmarkResult:
        if not self.registry.exists(model_name):
            raise KeyError(f"Model '{model_name}' is not registered.")
        model_type = self.registry.info(model_name).get("type", "custom")
        try:
            if model_type == "llm":
                metrics = self._run_llm(model_name)
            elif model_type == "stt":
                metrics = self._run_stt(model_name)
            elif model_type == "vad":
                metrics = self._run_vad(model_name)
            else:
                raise ValueError(f"Unsupported model type for benchmarking: {model_type}")
            result = BenchmarkResult(model=model_name, model_type=model_type, metrics=metrics.to_dict())
        except Exception as exc:
            if raise_on_error:
                raise
            result = BenchmarkResult(
                model=model_name,
                model_type=model_type,
                metrics={},
                success=False,
                metadata={"error": str(exc)},
            )
        finally:
            if self.registry.is_loaded(model_name):
                self.registry.unload(model_name)
        if self.memory_layer:
            model_info = self.registry.info(model_name)
            self.memory_layer.record_benchmark(
                model=model_name,
                model_type=model_type,
                metrics=result.metrics,
                parameters=model_info,
                metadata={"stability_runs": self.stability_runs},
                success=result.success,
                error=result.metadata.get("error") if result.metadata else None,
            )
        if save:
            self.reporter.save(result)
        return result

    def run_all(self, save: bool = True) -> List[BenchmarkResult]:
        results = []
        for name in self.registry.list_models():
            results.append(self.run(name, save=save, raise_on_error=False))
        return results

    def _run_llm(self, model_name: str) -> LLMMetrics:
        process = psutil.Process()
        start_ram = self._ram_mb(process)
        load_start = time.perf_counter()
        model_bundle = self.registry.load(model_name)
        load_ms = (time.perf_counter() - load_start) * 1000
        peak_ram = max(start_ram, self._ram_mb(process))
        peak_vram = self._reset_vram_peak()

        model = model_bundle["model"]
        tokenizer = model_bundle["tokenizer"]
        inputs = self._prepare_llm_inputs(model, tokenizer, DEFAULT_PROMPT)

        context = nullcontext()
        if importlib.util.find_spec("torch") is not None:
            import torch

            context = torch.no_grad()

        with context:
            first_start = time.perf_counter()
            model.generate(**inputs, max_new_tokens=1)
            first_ms = (time.perf_counter() - first_start) * 1000
            peak_ram = max(peak_ram, self._ram_mb(process))

            tokens_per_sec_samples: List[float] = []
            for _ in range(self.stability_runs):
                run_start = time.perf_counter()
                output = model.generate(**inputs, max_new_tokens=32)
                elapsed = time.perf_counter() - run_start
                generated = self._count_generated_tokens(output, inputs)
                tokens_per_sec_samples.append(generated / elapsed if elapsed > 0 else 0.0)
                peak_ram = max(peak_ram, self._ram_mb(process))

        peak_vram = max(peak_vram, self._get_peak_vram_mb())
        tokens_per_second = sum(tokens_per_sec_samples) / len(tokens_per_sec_samples)

        return LLMMetrics(
            loadtimems=round(load_ms, 2),
            firsttokenlatency_ms=round(first_ms, 2),
            tokenspersecond=round(tokens_per_second, 2),
            peakrammb=round(peak_ram, 2),
            peakvrammb=round(peak_vram, 2),
            stability_score=stability_score(tokens_per_sec_samples),
        )

    def _run_stt(self, model_name: str) -> STTMetrics:
        process = psutil.Process()
        start_ram = self._ram_mb(process)
        load_start = time.perf_counter()
        model = self.registry.load(model_name)
        load_ms = (time.perf_counter() - load_start) * 1000
        peak_ram = max(start_ram, self._ram_mb(process))

        sample_wav = self._ensure_sample_wav()
        audio_seconds = self._wav_duration_seconds(sample_wav)
        start = time.perf_counter()
        segments, _info = model.transcribe(str(sample_wav), beam_size=1)
        for _segment in segments:
            pass
        latency = time.perf_counter() - start
        peak_ram = max(peak_ram, self._ram_mb(process))

        rtf = latency / audio_seconds if audio_seconds else 0.0
        return STTMetrics(
            loadtimems=round(load_ms, 2),
            transcriptionlatencyms=round(latency * 1000, 2),
            realtimefactor=round(rtf, 3),
            peakrammb=round(peak_ram, 2),
        )

    def _run_vad(self, model_name: str) -> VADMetrics:
        if importlib.util.find_spec("torch") is None:
            raise RuntimeError("Torch is required for VAD benchmarking.")
        import torch

        process = psutil.Process()
        start_ram = self._ram_mb(process)
        load_start = time.perf_counter()
        model = self.registry.load(model_name)
        load_ms = (time.perf_counter() - load_start) * 1000
        peak_ram = max(start_ram, self._ram_mb(process))

        sample_wav = self._ensure_sample_wav()
        audio = self._load_wav_segment(sample_wav, seconds=1.0)
        waveform = torch.tensor(audio).float().unsqueeze(0)
        run_start = time.perf_counter()
        _ = model(waveform, 16000)
        latency_ms = (time.perf_counter() - run_start) * 1000
        peak_ram = max(peak_ram, self._ram_mb(process))

        return VADMetrics(
            loadtimems=round(load_ms, 2),
            processinglatencyms=round(latency_ms, 2),
        )

    @staticmethod
    def _prepare_llm_inputs(model: Any, tokenizer: Any, prompt: str) -> Dict[str, Any]:
        inputs = tokenizer(prompt, return_tensors="pt")
        device = getattr(model, "device", None)
        if device is None and hasattr(model, "parameters"):
            parameters = list(model.parameters())
            if parameters:
                device = parameters[0].device
        if device is not None:
            inputs = {key: value.to(device) for key, value in inputs.items()}
        return inputs

    @staticmethod
    def _count_generated_tokens(output: Any, inputs: Dict[str, Any]) -> int:
        if isinstance(output, (list, tuple)):
            output = output[0]
        output_length = output.shape[-1]
        input_length = inputs["input_ids"].shape[-1]
        return max(0, int(output_length - input_length))

    @staticmethod
    def _ram_mb(process: psutil.Process) -> float:
        return process.memory_info().rss / (1024 * 1024)

    @staticmethod
    def _wav_duration_seconds(path: Path) -> float:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
        return frames / float(rate)

    def _ensure_sample_wav(self) -> Path:
        if self.sample_wav.exists():
            return self.sample_wav
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self._write_sine_wave(self.sample_wav, seconds=5.0)
        return self.sample_wav

    @staticmethod
    def _write_sine_wave(path: Path, seconds: float, sample_rate: int = 16000) -> None:
        frames = int(sample_rate * seconds)
        amplitude = 0.2
        frequency = 440.0
        data = bytearray()
        for i in range(frames):
            sample = amplitude * math.sin(2 * math.pi * frequency * (i / sample_rate))
            value = int(sample * 32767)
            data.extend(value.to_bytes(2, "little", signed=True))
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(data)

    @staticmethod
    def _load_wav_segment(path: Path, seconds: float) -> List[float]:
        with wave.open(str(path), "rb") as wf:
            rate = wf.getframerate()
            frames = int(rate * seconds)
            data = wf.readframes(frames)
            samples = []
            for i in range(0, len(data), 2):
                sample = int.from_bytes(data[i : i + 2], "little", signed=True)
                samples.append(sample / 32768.0)
        return samples

    @staticmethod
    def _reset_vram_peak() -> float:
        if importlib.util.find_spec("torch") is None:
            return 0.0
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            return torch.cuda.max_memory_allocated() / (1024 * 1024)
        return 0.0

    @staticmethod
    def _get_peak_vram_mb() -> float:
        if importlib.util.find_spec("torch") is None:
            return 0.0
        import torch

        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / (1024 * 1024)
        return 0.0
