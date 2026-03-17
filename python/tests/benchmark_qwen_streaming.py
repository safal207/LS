#!/usr/bin/env python3
"""Benchmark: streaming latency + parser speed (Python vs Rust vs C++)."""

from __future__ import annotations

import ctypes
import json
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from modules.llm import qwen_handler

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class BenchResult:
    mode: str
    runs: int
    avg_ttft_ms: float
    p95_ttft_ms: float
    avg_total_ms: float
    p95_total_ms: float


class _FakeJsonResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeStreamResponse:
    def __init__(self, lines: list[str], per_token_delay_s: float):
        self._lines = lines
        self._per_token_delay_s = per_token_delay_s

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = True):
        for line in self._lines:
            time.sleep(self._per_token_delay_s)
            yield line


class _FakeSession:
    def __init__(self, token_count: int, per_token_delay_s: float):
        self.headers = {}
        self.token_count = token_count
        self.per_token_delay_s = per_token_delay_s

    def post(self, *args, **kwargs):
        if kwargs.get("stream"):
            lines = [json.dumps({"response": "x"}) for _ in range(self.token_count)]
            return _FakeStreamResponse(lines, self.per_token_delay_s)

        time.sleep(self.token_count * self.per_token_delay_s)
        return _FakeJsonResponse({"response": "x" * self.token_count})


class _FakeRequests:
    def __init__(self, token_count: int, per_token_delay_s: float):
        self.token_count = token_count
        self.per_token_delay_s = per_token_delay_s

    def Session(self):
        return _FakeSession(self.token_count, self.per_token_delay_s)


def _p95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))
    return ordered[idx]


def run_benchmark(runs: int = 8, token_count: int = 16, per_token_delay_s: float = 0.04) -> list[BenchResult]:
    original_requests = qwen_handler.requests
    qwen_handler.requests = _FakeRequests(token_count=token_count, per_token_delay_s=per_token_delay_s)
    try:
        handler = qwen_handler.QwenHandler(use_cloud_api=False)

        stream_ttft: list[float] = []
        stream_total: list[float] = []
        nonstream_ttft: list[float] = []
        nonstream_total: list[float] = []

        for _run in range(runs):
            first_token_at = None
            started = time.perf_counter()

            def _on_token(_: str) -> None:
                nonlocal first_token_at
                if first_token_at is None:
                    first_token_at = time.perf_counter()

            _stream_result = handler.generate_response("bench", stream=True, on_token=_on_token)
            ended = time.perf_counter()
            assert first_token_at is not None
            stream_ttft.append((first_token_at - started) * 1000)
            stream_total.append((ended - started) * 1000)

            started = time.perf_counter()
            _nonstream_result = handler.generate_response("bench", stream=False)
            ended = time.perf_counter()
            elapsed_ms = (ended - started) * 1000
            nonstream_ttft.append(elapsed_ms)
            nonstream_total.append(elapsed_ms)

        return [
            BenchResult("streaming", runs, statistics.fmean(stream_ttft), _p95(stream_ttft), statistics.fmean(stream_total), _p95(stream_total)),
            BenchResult("non_streaming", runs, statistics.fmean(nonstream_ttft), _p95(nonstream_ttft), statistics.fmean(nonstream_total), _p95(nonstream_total)),
        ]
    finally:
        qwen_handler.requests = original_requests


def _build_cpp_parser() -> tuple[Path | None, str]:
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "cpp" / "ollama_stream_parser.cpp"
    build_dir = repo_root / "cpp" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    cxx = shutil.which("g++") or shutil.which("clang++")
    if cxx is None:
        return None, "c++ compiler not found"

    out = build_dir / "libollama_stream_parser.so"
    cmd = [cxx, "-O3", "-std=c++17", "-shared", "-fPIC", str(src), "-o", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or "build failed").strip()
    return out, ""


def _benchmark_python_parser(frame: str, iterations: int) -> float:
    started = time.perf_counter()
    for _ in range(iterations):
        parsed = json.loads(frame)
        _token = parsed.get("response", "")
    return (time.perf_counter() - started) * 1000


def _benchmark_rust_parser(frame: str, iterations: int) -> tuple[float | None, str]:
    try:
        ghostgpt_core = getattr(qwen_handler, "_ghostgpt_core", None)
        if ghostgpt_core is None:
            import ghostgpt_core as _ghostgpt_core  # type: ignore
            ghostgpt_core = _ghostgpt_core

        started = time.perf_counter()
        for _ in range(iterations):
            _ = ghostgpt_core.extract_ollama_token(frame, False)
        return (time.perf_counter() - started) * 1000, ""
    except Exception as exc:
        return None, str(exc)


def _benchmark_cpp_parser(frame: str, iterations: int) -> tuple[float | None, str]:
    lib_path, err = _build_cpp_parser()
    if lib_path is None:
        return None, err

    try:
        lib = ctypes.CDLL(str(lib_path))
        fn = lib.extract_ollama_token_cpp
        fn.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        fn.restype = ctypes.c_int

        out = ctypes.create_string_buffer(1024)
        out_len = ctypes.c_int(0)
        payload = frame.encode("utf-8")

        started = time.perf_counter()
        for _ in range(iterations):
            _ = fn(payload, 0, out, len(out), ctypes.byref(out_len))
        return (time.perf_counter() - started) * 1000, ""
    except Exception as exc:
        return None, str(exc)


def benchmark_parser_speed(iterations: int = 20000) -> dict[str, float | str | None]:
    frame = json.dumps({"response": "token"})
    py_ms = _benchmark_python_parser(frame, iterations)
    rust_ms, rust_err = _benchmark_rust_parser(frame, iterations)
    cpp_ms, cpp_err = _benchmark_cpp_parser(frame, iterations)

    return {
        "iterations": float(iterations),
        "python_ms": py_ms,
        "rust_ms": rust_ms,
        "cpp_ms": cpp_ms,
        "rust_speedup": (py_ms / rust_ms) if rust_ms else None,
        "cpp_speedup": (py_ms / cpp_ms) if cpp_ms else None,
        "rust_error": rust_err,
        "cpp_error": cpp_err,
    }


def render_markdown(results: list[BenchResult], token_count: int, per_token_delay_s: float) -> str:
    header = "| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |\n|---|---:|---:|---:|---:|---:|"
    rows = [f"| {r.mode} | {r.runs} | {r.avg_ttft_ms:.2f} | {r.p95_ttft_ms:.2f} | {r.avg_total_ms:.2f} | {r.p95_total_ms:.2f} |" for r in results]
    speedup = next(r for r in results if r.mode == "non_streaming").avg_ttft_ms / next(r for r in results if r.mode == "streaming").avg_ttft_ms

    parser = benchmark_parser_speed()
    rust_line = (
        f"- Rust JSON token parser: `{parser['rust_ms']:.2f} ms` (~{parser['rust_speedup']:.2f}x vs Python)."
        if parser["rust_ms"] is not None
        else f"- Rust JSON token parser: unavailable ({parser['rust_error']})."
    )
    cpp_line = (
        f"- C++ JSON token parser: `{parser['cpp_ms']:.2f} ms` (~{parser['cpp_speedup']:.2f}x vs Python)."
        if parser["cpp_ms"] is not None
        else f"- C++ JSON token parser: unavailable ({parser['cpp_error']})."
    )

    lines = [
        "# Qwen Streaming Benchmark Results",
        "",
        "Deterministic synthetic benchmark (fake transport):",
        f"- tokens per response: `{token_count}`",
        f"- per-token generation delay: `{per_token_delay_s*1000:.0f} ms`",
        "",
        header,
        *rows,
        "",
        f"**TTFT improvement (streaming vs non-streaming): ~{speedup:.1f}x faster**.",
        "",
        "Parser micro-benchmark (20k frames):",
        f"- Python JSON parser: `{parser['python_ms']:.2f} ms`.",
        rust_line,
        cpp_line,
        "",
        "Interpretation: streaming gives major TTFT gain; native parsers (Rust/C++) reduce CPU overhead in token frame parsing.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    res = run_benchmark(runs=8, token_count=16, per_token_delay_s=0.04)
    print(render_markdown(res, token_count=16, per_token_delay_s=0.04))
