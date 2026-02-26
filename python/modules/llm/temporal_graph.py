from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Callable


def _parse_ts(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _extract_thread_id(entry: dict[str, Any]) -> str:
    ltp = entry.get("ltp_trace") or {}
    if isinstance(ltp, dict) and ltp.get("thread_id"):
        return str(ltp["thread_id"])
    lce = entry.get("lce") or {}
    memory = lce.get("memory") if isinstance(lce, dict) else {}
    if isinstance(memory, dict) and memory.get("thread"):
        return str(memory["thread"])
    return "unknown"


def _extract_focus(entry: dict[str, Any]) -> float | None:
    lri = entry.get("lri_core") or {}
    resonance = lri.get("resonance_map") if isinstance(lri, dict) else {}
    if not isinstance(resonance, dict):
        return None
    value = resonance.get("focus")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cosine_similarity_scalar(a: float, b: float) -> float:
    denom = max(abs(a) * abs(b), 1e-12)
    return max(0.0, min(1.0, (a * b) / denom))


def _contains_case_insensitive(text: str, snippet: str) -> bool:
    return bool(snippet.strip()) and snippet.lower() in text.lower()


def build_graph(replay_loader: Callable[[], list[dict[str, Any]]]) -> dict[str, Any]:
    entries = replay_loader() or []

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen = set()

    ordered: list[tuple[str, datetime, dict[str, Any]]] = []
    by_thread: dict[str, list[tuple[str, datetime]]] = defaultdict(list)

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ts = _parse_ts(entry.get("ts"))
        thread_id = _extract_thread_id(entry)
        node_id = f"{thread_id}:{int(ts.timestamp() * 1000)}"

        nodes[node_id] = {
            "id": node_id,
            "cause": entry.get("cause", ""),
            "solution": entry.get("solution", ""),
            "ts": ts.isoformat(),
            "lri_core": entry.get("lri_core", {}),
            "edges": [],
        }
        ordered.append((node_id, ts, entry))
        by_thread[thread_id].append((node_id, ts))

    def add_edge(src: str, dst: str, weight: float, relation: str) -> None:
        key = (src, dst, relation)
        if key in seen:
            return
        seen.add(key)
        edges.append({"from": src, "to": dst, "weight": weight, "relation": relation})
        nodes[src]["edges"].append(dst)

    for thread_nodes in by_thread.values():
        thread_nodes.sort(key=lambda item: item[1])
        for (src, src_ts), (dst, dst_ts) in zip(thread_nodes, thread_nodes[1:]):
            delta = abs((dst_ts - src_ts).total_seconds())
            add_edge(src, dst, 1.0 / (delta + 1.0), "temporal")

    ordered.sort(key=lambda item: item[1])
    for idx, (left_id, _left_ts, left_entry) in enumerate(ordered):
        for right_id, _right_ts, right_entry in ordered[idx + 1 :]:
            left_solution = str(left_entry.get("solution", ""))
            right_solution = str(right_entry.get("solution", ""))
            left_cause = str(left_entry.get("cause", ""))
            right_cause = str(right_entry.get("cause", ""))

            if _contains_case_insensitive(right_cause, left_solution):
                add_edge(left_id, right_id, 1.0, "causal")
            if _contains_case_insensitive(left_cause, right_solution):
                add_edge(right_id, left_id, 1.0, "causal")

            left_focus = _extract_focus(left_entry)
            right_focus = _extract_focus(right_entry)
            if left_focus is not None and right_focus is not None:
                similarity = _cosine_similarity_scalar(left_focus, right_focus)
                if similarity > 0.0:
                    add_edge(left_id, right_id, similarity, "resonance")
                    add_edge(right_id, left_id, similarity, "resonance")

    return {"nodes": nodes, "edges": edges}


def find_related(graph: dict[str, Any], thread_id: str, max_depth: int = 2) -> list[str]:
    nodes = graph.get("nodes", {})
    starts = [node_id for node_id in nodes if node_id.startswith(f"{thread_id}:")]
    if not starts:
        return []

    related_threads: set[str] = set()
    visited = set(starts)
    queue = deque((node_id, 0) for node_id in starts)

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor in nodes.get(current, {}).get("edges", []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, depth + 1))
            related_threads.add(neighbor.split(":", 1)[0])

    related_threads.discard(thread_id)
    return sorted(related_threads)


def visualize_ascii(graph: dict[str, Any]) -> str:
    nodes = graph.get("nodes", {})
    edges_by_src: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        edges_by_src[edge["from"]].append(
            f"{edge['relation']}({edge['weight']:.2f})-> {edge['to']}"
        )

    lines = ["Temporal Graph"]
    for node_id in sorted(nodes.keys()):
        cause = str(nodes[node_id].get("cause", ""))[:40]
        lines.append(f"* {node_id} | cause={cause}")
        for edge_repr in sorted(edges_by_src.get(node_id, [])):
            lines.append(f"  └─ {edge_repr}")
    return "\n".join(lines)


def build_temporal_graph(
    replay_loader: Callable[[], list[dict[str, Any]]]
) -> dict[str, Any]:
    return build_graph(replay_loader)


def find_related_threads(
    graph: dict[str, Any],
    thread_id: str,
    max_depth: int = 2,
) -> set[str]:
    return set(find_related(graph, thread_id, max_depth=max_depth))


def format_memory_context(
    related_thread_ids: set[str],
    graph: dict[str, Any],
    max_entries: int = 3,
) -> str:
    nodes = graph.get("nodes", {})
    lines = ["[Из памяти системы — похожие ситуации]", ""]
    count = 0
    for node_id, node in nodes.items():
        node_thread = node.get("thread_id") or node_id.split(":", 1)[0]
        if node_thread not in related_thread_ids:
            continue
        cause = str(node.get("cause", ""))[:80]
        solution = str(node.get("solution", ""))[:80]
        lines.append(f"Причина: {cause}")
        lines.append(f"Решение: {solution}")
        lines.append("")
        count += 1
        if count >= max_entries:
            break
    return "\n".join(lines).strip() if count > 0 else ""


def get_context_for_question(
    question: str,
    thread_id: str,
    *,
    replay_loader: Callable[[], list[dict[str, Any]]],
    max_depth: int = 2,
    max_entries: int = 3,
) -> str:
    """
    Строит граф, находит похожие треды, возвращает контекст для LLM.

    max_depth: максимальная дистанция в графе (по умолчанию 2)
    max_entries: сколько причин+решений показывать (по умолчанию 3)
    """
    graph = build_temporal_graph(replay_loader)
    related_ids = find_related_threads(graph, thread_id, max_depth)
    if not related_ids:
        return ""
    return format_memory_context(related_ids, graph, max_entries)
