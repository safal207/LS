from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal
import copy
import re
import time


@dataclass
class ModeAResponse:
    """Response from Mode A (Fast Mode)."""

    result: str
    source: Literal[
        "cache",
        "temporal_lookup",
        "string_command",
        "math",
        "mini_nlu",
        "echo",
    ]
    execution_time_ms: float
    cache_hit: bool
    load_factor: float

    def to_dict(self) -> dict:
        return {
            "result": self.result,
            "source": self.source,
            "execution_time_ms": self.execution_time_ms,
            "cache_hit": self.cache_hit,
            "load_factor": self.load_factor,
        }


class FastMode:
    """
    Fast Mode (Mode A)

    Lightweight, reactive processing:
    - No reasoning
    - No context mutation
    - Deterministic (except time/date)
    - Load-aware

    Guaranteed O(n) or better.
    """

    def __init__(self, cache_size: int = 128) -> None:
        self.cache_size = cache_size
        self.cache: OrderedDict[str, str] = OrderedDict()
        self.greetings = {"hi", "hey", "hello", "greetings", "sup", "yo"}
        self.gratitude = {"thanks", "thank you", "thx", "ty", "appreciate"}
        self._stats = self._init_stats()

    def _init_stats(self) -> dict:
        return {
            "inputs": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "load_shed": 0,
            "load_shed_by_source": {
                "string_command": 0,
                "math": 0,
            },
            "heuristics": {
                "temporal_lookup": 0,
                "math": 0,
                "string_command": 0,
                "mini_nlu": 0,
                "echo": 0,
            },
            "input_length": {
                "count": 0,
                "min": None,
                "max": None,
                "total": 0,
                "avg": 0.0,
                "buckets": {
                    "0-4": 0,
                    "5-10": 0,
                    "11-50": 0,
                    "51-100": 0,
                    "101+": 0,
                },
            },
        }

    def get_stats(self) -> dict:
        return copy.deepcopy(self._stats)

    def reset_stats(self) -> None:
        self._stats = self._init_stats()

    def process(self, input_data: str, system_load: float = 0.0) -> ModeAResponse:
        start_time = time.perf_counter()
        raw = input_data or ""
        text = raw.strip()
        lower = text.lower()
        key = lower

        self._record_input(len(text))

        load_shed = system_load > 0.8
        heavy_source = self._heavy_under_load(lower)
        if load_shed and heavy_source is not None:
            self._record_load_shed(heavy_source)
            return self._response(
                "Not available (system under load)",
                heavy_source,
                start_time,
                False,
                system_load,
            )

        cache_hit, cached = self._check_cache(key)
        if cache_hit:
            self._record_cache(True)
            return self._response(cached, "cache", start_time, True, system_load)
        if key:
            self._record_cache(False)

        result, source = self._try_temporal(lower)
        if result is not None:
            self._cache_result(key, result)
            self._record_source(source)
            return self._response(result, source, start_time, False, system_load)

        result, source = self._try_math(lower, system_load)
        if result is not None:
            self._cache_result(key, result)
            self._record_source(source)
            return self._response(result, source, start_time, False, system_load)

        result, source = self._try_string_command(text, system_load)
        if result is not None:
            self._cache_result(key, result)
            self._record_source(source)
            return self._response(result, source, start_time, False, system_load)

        result, source = self._try_mini_nlu(lower)
        if result is not None:
            self._cache_result(key, result)
            self._record_source(source)
            return self._response(result, source, start_time, False, system_load)

        result, source = self._echo(raw)
        self._cache_result(key, result)
        self._record_source(source)
        return self._response(result, source, start_time, False, system_load)

    # ==================== HEURISTICS ====================

    def _try_temporal(self, lower: str) -> tuple[Optional[str], Optional[str]]:
        if lower == "time":
            return datetime.now().strftime("%H:%M"), "temporal_lookup"
        if lower == "date":
            return datetime.now().strftime("%Y-%m-%d"), "temporal_lookup"
        if lower == "day":
            return datetime.now().strftime("%A"), "temporal_lookup"
        if lower == "now":
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "temporal_lookup"
        return None, None

    def _try_math(self, lower: str, system_load: float) -> tuple[Optional[str], Optional[str]]:
        expr = lower.replace(" ", "")
        if not expr:
            return None, None
        if not re.fullmatch(r"[0-9+*/-]+", expr):
            return None, None

        tokens = re.findall(r"\d+|[+*/-]", expr)
        if not tokens or len(tokens) < 3:
            return None, None

        # Ensure alternating number/operator
        if len(tokens) % 2 == 0:
            return None, None
        for i, tok in enumerate(tokens):
            if i % 2 == 0 and not tok.isdigit():
                return None, None
            if i % 2 == 1 and tok not in {"+", "-", "*", "/"}:
                return None, None

        ops = tokens[1::2]
        op_count = len(ops)
        if op_count > 3:
            return None, None
        if system_load > 0.8 and op_count > 1:
            return None, None

        try:
            result = float(tokens[0])
            for op, num in zip(ops, tokens[2::2]):
                val = float(num)
                if op == "+":
                    result += val
                elif op == "-":
                    result -= val
                elif op == "*":
                    result *= val
                elif op == "/":
                    if val == 0:
                        return None, None
                    result /= val
        except Exception:
            return None, None

        if "/" in ops:
            return str(result), "math"
        if result.is_integer():
            return str(int(result)), "math"
        return str(result), "math"

    def _try_string_command(self, text: str, system_load: float) -> tuple[Optional[str], Optional[str]]:
        parts = text.split(None, 1)
        if len(parts) != 2:
            return None, None

        cmd = parts[0].lower()
        arg = parts[1]

        if system_load > 0.8 and cmd in {"rev", "words"}:
            return "Not available (system under load)", "string_command"

        if cmd == "len":
            return str(len(arg)), "string_command"
        if cmd == "rev":
            return arg[::-1], "string_command"
        if cmd == "trim":
            return arg.strip(), "string_command"
        if cmd == "upper":
            return arg.upper(), "string_command"
        if cmd == "lower":
            return arg.lower(), "string_command"
        if cmd == "words":
            return str(len(arg.split())), "string_command"
        if cmd == "echo":
            return arg, "string_command"

        return None, None

    def _try_mini_nlu(self, lower: str) -> tuple[Optional[str], Optional[str]]:
        if any(g in lower for g in self.greetings):
            return "Hello! How can I help?", "mini_nlu"
        if any(t in lower for t in self.gratitude):
            return "You're welcome!", "mini_nlu"
        return None, None

    def _echo(self, raw: str) -> tuple[str, str]:
        return raw, "echo"

    def _heavy_under_load(self, lower: str) -> Optional[str]:
        if lower.startswith("rev ") or lower.startswith("words "):
            return "string_command"
        expr = lower.replace(" ", "")
        if not re.fullmatch(r"[0-9+*/-]+", expr or ""):
            return None
        tokens = re.findall(r"\d+|[+*/-]", expr)
        if not tokens or len(tokens) < 3:
            return None
        ops = tokens[1::2]
        if len(ops) > 1:
            return "math"
        return None

    # ==================== CACHING ====================

    def _check_cache(self, key: str) -> tuple[bool, Optional[str]]:
        if not key:
            return False, None
        if key in self.cache:
            self.cache.move_to_end(key)
            return True, self.cache[key]
        return False, None

    def _cache_result(self, key: str, value: str) -> None:
        if not key:
            return
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)

    def clear_cache(self) -> None:
        self.cache.clear()

    # ==================== TELEMETRY ====================

    def _record_input(self, length: int) -> None:
        stats = self._stats
        stats["inputs"] += 1
        length_stats = stats["input_length"]
        length_stats["count"] += 1
        length_stats["total"] += length
        length_stats["min"] = length if length_stats["min"] is None else min(length_stats["min"], length)
        length_stats["max"] = length if length_stats["max"] is None else max(length_stats["max"], length)
        length_stats["avg"] = (
            length_stats["total"] / length_stats["count"] if length_stats["count"] else 0.0
        )

        if length <= 4:
            bucket = "0-4"
        elif length <= 10:
            bucket = "5-10"
        elif length <= 50:
            bucket = "11-50"
        elif length <= 100:
            bucket = "51-100"
        else:
            bucket = "101+"
        length_stats["buckets"][bucket] += 1

    def _record_cache(self, hit: bool) -> None:
        if hit:
            self._stats["cache_hits"] += 1
        else:
            self._stats["cache_misses"] += 1

    def _record_source(self, source: Optional[str]) -> None:
        if not source:
            return
        counts = self._stats["heuristics"]
        if source in counts:
            counts[source] += 1

    def _record_load_shed(self, source: Optional[str]) -> None:
        self._stats["load_shed"] += 1
        if not source:
            return
        by_source = self._stats["load_shed_by_source"]
        if source in by_source:
            by_source[source] += 1

    # ==================== RESPONSE ====================

    def _response(
        self,
        result: str,
        source: str,
        start_time: float,
        cache_hit: bool,
        load_factor: float,
    ) -> ModeAResponse:
        exec_ms = (time.perf_counter() - start_time) * 1000.0
        return ModeAResponse(
            result=result,
            source=source,  # type: ignore[arg-type]
            execution_time_ms=exec_ms,
            cache_hit=cache_hit,
            load_factor=load_factor,
        )


# Backward compatibility alias
ModeA = FastMode
