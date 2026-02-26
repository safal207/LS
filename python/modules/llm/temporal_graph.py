from __future__ import annotations

import math
import re
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


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _build_tfidf_matrix(texts: list[str]) -> tuple[list[list[float]], dict[str, int], list[float]]:
    tokenized = [_tokenize(text) for text in texts]
    vocabulary: dict[str, int] = {}
    for tokens in tokenized:
        for token in tokens:
            if token not in vocabulary:
                vocabulary[token] = len(vocabulary)

    matrix = [[0.0 for _ in range(len(vocabulary))] for _ in range(len(texts))]
    document_frequency = [0.0 for _ in range(len(vocabulary))]

    for row_idx, tokens in enumerate(tokenized):
        if not tokens:
            continue
        token_counts: dict[str, int] = defaultdict(int)
        for token in tokens:
            token_counts[token] += 1
        for token, count in token_counts.items():
            col_idx = vocabulary[token]
            matrix[row_idx][col_idx] = count / len(tokens)
            document_frequency[col_idx] += 1

    idf = [math.log((1.0 + len(texts)) / (1.0 + value)) + 1.0 for value in document_frequency]
    for row in matrix:
        for idx, weight in enumerate(row):
            row[idx] = weight * idf[idx]
    return matrix, vocabulary, idf


def _vectorize_query(query: str, vocabulary: dict[str, int], idf: list[float]) -> list[float]:
    vector = [0.0 for _ in range(len(vocabulary))]
    tokens = _tokenize(query)
    if not tokens:
        return vector

    token_counts: dict[str, int] = defaultdict(int)
    for token in tokens:
        if token in vocabulary:
            token_counts[token] += 1

    if not token_counts:
        return vector

    token_total = sum(token_counts.values())
    for token, count in token_counts.items():
        col_idx = vocabulary[token]
        vector[col_idx] = (count / token_total) * idf[col_idx]
    return vector


def _cosine_similarity(query_vector: list[float], matrix: list[list[float]]) -> list[float]:
    query_norm = math.sqrt(sum(value * value for value in query_vector))
    similarities: list[float] = []
    for row in matrix:
        row_norm = math.sqrt(sum(value * value for value in row))
        denom = max(row_norm * query_norm, 1e-12)
        dot_product = sum(left * right for left, right in zip(row, query_vector))
        similarities.append(dot_product / denom)
    return similarities


def _score_related_threads(
    graph: dict[str, Any], thread_id: str, max_depth: int = 2
) -> dict[str, float]:
    nodes = graph.get("nodes", {})
    starts = [node_id for node_id in nodes if node_id.startswith(f"{thread_id}:")]
    if not starts:
        return {}

    scores: dict[str, float] = defaultdict(float)
    queue = deque((node_id, 0) for node_id in starts)
    best_depth: dict[str, int] = {node_id: 0 for node_id in starts}

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        current_node = nodes.get(current, {})
        for neighbor in current_node.get("edges", []):
            next_depth = depth + 1
            prev_depth = best_depth.get(neighbor)
            if prev_depth is not None and prev_depth <= next_depth:
                continue
            best_depth[neighbor] = next_depth
            queue.append((neighbor, next_depth))

            node_thread = neighbor.split(":", 1)[0]
            if node_thread == thread_id:
                continue
            scores[neighbor] += 1.0 / float(next_depth)
    return dict(scores)


def find_vector_related(
    graph: dict[str, Any],
    thread_id: str,
    query_text: str,
    top_k: int = 5,
    min_similarity: float = 0.2,
) -> dict[str, float]:
    nodes = graph.get("nodes", {})
    node_ids = list(nodes.keys())
    if not node_ids:
        return {}

    texts = [f"{nodes[node_id].get('cause', '')} {nodes[node_id].get('solution', '')}" for node_id in node_ids]
    matrix, vocabulary, idf = _build_tfidf_matrix(texts)
    query_vec = _vectorize_query(query_text, vocabulary, idf)
    similarities = _cosine_similarity(query_vec, matrix)

    ranked = sorted(enumerate(similarities), key=lambda item: item[1], reverse=True)
    related: dict[str, float] = {}
    for idx, similarity in ranked[:top_k]:
        if similarity < min_similarity:
            continue
        node_id = node_ids[idx]
        if node_id.split(":", 1)[0] == thread_id:
            continue
        related[node_id] = float(similarity)
    return related


def format_memory_context(
    related_thread_ids: set[str],
    graph: dict[str, Any],
    max_entries: int = 3,
    ranked_node_ids: list[str] | None = None,
) -> str:
    nodes = graph.get("nodes", {})
    lines = ["[Из памяти системы — похожие ситуации]", ""]
    count = 0
    ordered_node_ids = ranked_node_ids or list(nodes.keys())
    for node_id in ordered_node_ids:
        node = nodes.get(node_id, {})
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
    graph_scores = _score_related_threads(graph, thread_id, max_depth=max_depth)
    vector_scores = find_vector_related(graph, thread_id, question)

    combined_scores: dict[str, float] = defaultdict(float)
    for node_id, score in graph_scores.items():
        combined_scores[node_id] += score
    for node_id, score in vector_scores.items():
        combined_scores[node_id] += score

    if not combined_scores:
        return ""

    ranked_node_ids = [
        node_id
        for node_id, _score in sorted(
            combined_scores.items(), key=lambda item: item[1], reverse=True
        )
    ]

    related_ids = {node_id.split(":", 1)[0] for node_id in ranked_node_ids}
    return format_memory_context(
        related_ids,
        graph,
        max_entries,
        ranked_node_ids=ranked_node_ids,
    )
