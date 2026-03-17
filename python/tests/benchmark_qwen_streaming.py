#!/usr/bin/env python3
"""Micro-benchmark: streaming vs non-streaming path in QwenHandler.

Uses deterministic fake HTTP backend so we can compare TTFT and total time in CI/dev
without depending on local Ollama availability.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass

from modules.llm import qwen_handler


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
    # inclusive quantiles-like approximation for small sample
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

        for _ in range(runs):
            # streaming run
            first_token_at = None
            started = time.perf_counter()

            def _on_token(_: str) -> None:
                nonlocal first_token_at
                if first_token_at is None:
                    first_token_at = time.perf_counter()

            _ = handler.generate_response("bench", stream=True, on_token=_on_token)
            ended = time.perf_counter()
            assert first_token_at is not None
            stream_ttft.append((first_token_at - started) * 1000)
            stream_total.append((ended - started) * 1000)

            # non-streaming run
            started = time.perf_counter()
            _ = handler.generate_response("bench", stream=False)
            ended = time.perf_counter()
            elapsed_ms = (ended - started) * 1000
            nonstream_ttft.append(elapsed_ms)
            nonstream_total.append(elapsed_ms)

        return [
            BenchResult(
                mode="streaming",
                runs=runs,
                avg_ttft_ms=statistics.fmean(stream_ttft),
                p95_ttft_ms=_p95(stream_ttft),
                avg_total_ms=statistics.fmean(stream_total),
                p95_total_ms=_p95(stream_total),
            ),
            BenchResult(
                mode="non_streaming",
                runs=runs,
                avg_ttft_ms=statistics.fmean(nonstream_ttft),
                p95_ttft_ms=_p95(nonstream_ttft),
                avg_total_ms=statistics.fmean(nonstream_total),
                p95_total_ms=_p95(nonstream_total),
            ),
        ]
    finally:
        qwen_handler.requests = original_requests


def render_markdown(results: list[BenchResult], token_count: int, per_token_delay_s: float) -> str:
    header = "| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |\n|---|---:|---:|---:|---:|---:|"
    rows = [
        f"| {r.mode} | {r.runs} | {r.avg_ttft_ms:.2f} | {r.p95_ttft_ms:.2f} | {r.avg_total_ms:.2f} | {r.p95_total_ms:.2f} |"
        for r in results
    ]
    speedup = next(r for r in results if r.mode == "non_streaming").avg_ttft_ms / next(
        r for r in results if r.mode == "streaming"
    ).avg_ttft_ms
    parser = benchmark_parser_speed()
    rust_line = (
        f"- Rust JSON token parser: `{parser['rust_ms']:.2f} ms` for {int(parser['iterations'])} frames (~{parser['speedup']:.2f}x vs Python)."
        if parser["rust_ms"] is not None and parser["speedup"] is not None
        else f"- Rust JSON token parser: unavailable ({parser.get('error','unknown')})."
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
        "Parser micro-benchmark:",
        f"- Python JSON parser: `{parser['python_ms']:.2f} ms` for {int(parser['iterations'])} frames.",
        rust_line,
        "",
        "Interpretation: streaming drastically reduces *time-to-first-token*, while full completion time remains approximately equal.",
    ]
    return "\n".join(lines) + "\n"

def benchmark_parser_speed(iterations: int = 20000) -> dict[str, float | None | str]:
    frame = json.dumps({"response": "token"})

    started = time.perf_counter()
    for _ in range(iterations):
        parsed = json.loads(frame)
        _ = parsed.get("response", "")
    py_ms = (time.perf_counter() - started) * 1000

    rust_ms: float | None = None
    speedup: float | None = None
    try:
        import ghostgpt_core

        started = time.perf_counter()
        for _ in range(iterations):
            _ = ghostgpt_core.extract_ollama_token(frame, False)
        rust_ms = (time.perf_counter() - started) * 1000
        if rust_ms > 0:
            speedup = py_ms / rust_ms
    except Exception as exc:
        return {"python_ms": py_ms, "rust_ms": None, "speedup": None, "iterations": float(iterations), "error": str(exc)}

    return {"python_ms": py_ms, "rust_ms": rust_ms, "speedup": speedup, "iterations": float(iterations), "error": ""}


if __name__ == "__main__":
    RUNS = 8
    TOKENS = 16
    DELAY = 0.04
    res = run_benchmark(runs=RUNS, token_count=TOKENS, per_token_delay_s=DELAY)
    print(render_markdown(res, token_count=TOKENS, per_token_delay_s=DELAY))
