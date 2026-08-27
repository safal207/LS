from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass
import hashlib
import html
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import quote

REGISTRY_SCHEMA = "ls.cml-trust-registry.v0.1"
EVIDENCE_SCHEMA = "ls.cml-evidence.v0.1"
MEMORY_SCHEMA = "cml-memory-pack-v1"
MEMORY_ROOT = ".cml/memory/cycles"
MAX_SOURCES = 5
MAX_MEMORY_FILES = 500
MAX_FILE_BYTES = 1_000_000
MAX_REGISTRY_BYTES = 1_000_000
MAX_RESULTS = 3
MIN_SCORE = 0.05
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
CAMEL_BOUNDARY = re.compile(r"(?<=[a-zа-яіїє])(?=[A-ZА-ЯІЇЄ])")

TOP_FIELDS = {
    "schema_version",
    "pack_id",
    "manifest",
    "graph",
    "evidence",
    "redactions",
}
MANIFEST_FIELDS = {
    "project",
    "source_repository",
    "source_commit",
    "created_at",
    "visibility",
    "license",
    "contains_private_data",
    "merge_authority",
    "execution_authority",
    "description",
}
GRAPH_FIELDS = {"nodes", "edges", "selected_path"}
NODE_FIELDS = {"id", "kind", "label", "status", "confidence", "attributes"}
EDGE_FIELDS = {
    "id",
    "source",
    "target",
    "relation",
    "strength",
    "evidence_ids",
}
EVIDENCE_FIELDS = {"id", "kind", "digest", "locator", "description"}
REDACTION_FIELDS = {"path", "reason"}
NODE_WEIGHTS = {
    "situation": 5,
    "cause": 4,
    "constraint": 4,
    "option": 3,
    "action": 5,
    "check": 2,
    "outcome": 3,
    "lesson": 6,
    "evidence": 1,
}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "into", "is", "it", "of", "on", "or", "pr",
    "pull", "request", "that", "the", "this", "to", "was", "were", "with",
    "без", "для", "его", "как", "на", "не", "по", "при", "это", "та",
    "такий", "така", "таки", "що", "і", "й", "в", "у", "з",
}


class CmlError(ValueError):
    """Raised when a registry or public CML source violates the contract."""


@dataclass(frozen=True)
class Source:
    repository: str
    commit: str


@dataclass(frozen=True)
class Registry:
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class MemoryDocument:
    source_repository: str
    registry_commit: str
    path: str
    pack_id: str
    source_commit: str
    situation: str
    selected_path: tuple[str, ...]
    constraints: tuple[str, ...]
    token_weights: Mapping[str, int]
    evidence_count: int


@dataclass(frozen=True)
class RetrievalMatch:
    document: MemoryDocument
    score: float
    matched_terms: tuple[str, ...]


def _reject_constant(value: str) -> None:
    raise CmlError(f"non-finite JSON constant is not allowed: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CmlError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _loads(text: str, *, label: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CmlError(f"invalid JSON: {label}") from exc


def _mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CmlError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CmlError(f"{label} must be an array")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise CmlError(f"{label} must be a string")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise CmlError(f"{label} must contain only Unicode scalar values")
    return value


def _require_fields(
    payload: Mapping[str, Any], *, expected: set[str], label: str
) -> None:
    if set(payload) != expected:
        raise CmlError(f"invalid {label} fields")


def _full_sha(value: object, *, label: str) -> str:
    result = _string(value, label=label).strip().lower()
    if not SHA40.fullmatch(result):
        raise CmlError(f"{label} must be a full lowercase Git SHA")
    return result


def compact_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def load_registry(path: Path) -> Registry:
    if path.is_symlink():
        raise CmlError("CML registry must not be a symbolic link")
    try:
        if path.stat().st_size > MAX_REGISTRY_BYTES:
            raise CmlError("CML registry exceeds the safe size bound")
        payload = _mapping(
            _loads(path.read_text(encoding="utf-8"), label="CML registry"),
            label="CML registry",
        )
    except OSError as exc:
        raise CmlError("cannot read CML registry") from exc
    _require_fields(
        payload, expected={"schema_version", "sources"}, label="registry"
    )
    if payload.get("schema_version") != REGISTRY_SCHEMA:
        raise CmlError("unsupported CML registry schema")
    raw_sources = _sequence(payload.get("sources"), label="registry sources")
    if not raw_sources or len(raw_sources) > MAX_SOURCES:
        raise CmlError(f"registry must contain between 1 and {MAX_SOURCES} sources")
    sources: list[Source] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_sources:
        item = _mapping(raw, label="registry source")
        _require_fields(
            item, expected={"repository", "commit"}, label="registry source"
        )
        repository = _string(item.get("repository"), label="source repository")
        if not REPOSITORY.fullmatch(repository):
            raise CmlError("source repository must use owner/name format")
        commit = _full_sha(item.get("commit"), label="source commit")
        key = (repository, commit)
        if key in seen:
            raise CmlError("duplicate CML source")
        seen.add(key)
        sources.append(Source(repository=repository, commit=commit))
    return Registry(tuple(sources))


def _normalized_identifier_text(value: str) -> str:
    value = CAMEL_BOUNDARY.sub(" ", value)
    return re.sub(r"[/\\._:\-]+", " ", value)


def tokenize(value: str) -> tuple[str, ...]:
    normalized = _normalized_identifier_text(value).lower()
    result: list[str] = []
    for token in TOKEN_RE.findall(normalized):
        if len(token) < 2 or len(token) > 64:
            continue
        if token.isdigit() or token in STOPWORDS:
            continue
        result.append(token)
    return tuple(result)


def _add_tokens(counter: Counter[str], value: str, weight: int) -> None:
    for token in tokenize(value):
        counter[token] += weight


def build_query_weights(*, title: str, filenames: Sequence[str]) -> Counter[str]:
    result: Counter[str] = Counter()
    _add_tokens(result, title[:1000], 4)
    for filename in filenames[:300]:
        _add_tokens(result, filename[:512], 3)
    return result


def _canonical_preimage(pack: Mapping[str, Any]) -> dict[str, Any]:
    graph = _mapping(pack.get("graph"), label="graph")
    return {
        "schema_version": pack.get("schema_version"),
        "manifest": pack.get("manifest"),
        "graph": {
            "nodes": sorted(
                _sequence(graph.get("nodes"), label="nodes"),
                key=lambda item: item["id"],
            ),
            "edges": sorted(
                _sequence(graph.get("edges"), label="edges"),
                key=lambda item: item["id"],
            ),
            "selected_path": graph.get("selected_path"),
        },
        "evidence": sorted(
            _sequence(pack.get("evidence"), label="evidence"),
            key=lambda item: item["id"],
        ),
        "redactions": sorted(
            _sequence(pack.get("redactions"), label="redactions"),
            key=lambda item: (item["path"], item["reason"]),
        ),
    }


def _validate_schema(pack: Mapping[str, Any]) -> None:
    _require_fields(pack, expected=TOP_FIELDS, label="top-level")
    if pack.get("schema_version") != MEMORY_SCHEMA:
        raise CmlError("unexpected Memory Pack schema")
    manifest = _mapping(pack.get("manifest"), label="manifest")
    graph = _mapping(pack.get("graph"), label="graph")
    _require_fields(manifest, expected=MANIFEST_FIELDS, label="manifest")
    _require_fields(graph, expected=GRAPH_FIELDS, label="graph")
    for raw in _sequence(graph.get("nodes"), label="nodes"):
        _require_fields(
            _mapping(raw, label="node"), expected=NODE_FIELDS, label="node"
        )
    for raw in _sequence(graph.get("edges"), label="edges"):
        _require_fields(
            _mapping(raw, label="edge"), expected=EDGE_FIELDS, label="edge"
        )
    for raw in _sequence(pack.get("evidence"), label="evidence"):
        _require_fields(
            _mapping(raw, label="evidence item"),
            expected=EVIDENCE_FIELDS,
            label="evidence",
        )
    for raw in _sequence(pack.get("redactions"), label="redactions"):
        _require_fields(
            _mapping(raw, label="redaction"),
            expected=REDACTION_FIELDS,
            label="redaction",
        )


def parse_memory_pack(
    text: str,
    *,
    path: str,
    source_repository: str,
    registry_commit: str,
) -> MemoryDocument | None:
    if not path.startswith(f"{MEMORY_ROOT}/") or not path.endswith(".json"):
        raise CmlError("memory path is outside the accepted root")
    pack = _mapping(_loads(text, label="Memory Pack"), label="Memory Pack")
    _validate_schema(pack)
    pack_id = _string(pack.get("pack_id"), label="pack_id")
    if not SHA64.fullmatch(pack_id):
        raise CmlError("pack_id must be a lowercase SHA-256 digest")
    if sha256_json(_canonical_preimage(pack)) != pack_id:
        raise CmlError("Memory Pack identity mismatch")

    manifest = _mapping(pack.get("manifest"), label="manifest")
    if manifest.get("source_repository") != f"https://github.com/{source_repository}":
        raise CmlError("Memory Pack repository binding mismatch")
    source_commit = _full_sha(manifest.get("source_commit"), label="memory source commit")
    visibility = _string(manifest.get("visibility"), label="visibility")
    if visibility not in {"private", "team", "partner", "public"}:
        raise CmlError("unsupported Memory Pack visibility")
    contains_private_data = manifest.get("contains_private_data")
    if not isinstance(contains_private_data, bool):
        raise CmlError("contains_private_data must be boolean")
    if manifest.get("merge_authority") is not False:
        raise CmlError("Memory Pack must not grant merge authority")
    if manifest.get("execution_authority") is not False:
        raise CmlError("Memory Pack must not grant execution authority")

    graph = _mapping(pack.get("graph"), label="graph")
    raw_nodes = _sequence(graph.get("nodes"), label="nodes")
    raw_edges = _sequence(graph.get("edges"), label="edges")
    selected_ids = _sequence(graph.get("selected_path"), label="selected_path")
    if not selected_ids or len(selected_ids) != len(set(selected_ids)):
        raise CmlError("selected_path must be non-empty without duplicates")

    nodes: dict[str, dict[str, Any]] = {}
    token_weights: Counter[str] = Counter()
    constraints: list[str] = []
    for raw in raw_nodes:
        node = _mapping(raw, label="node")
        node_id = _string(node.get("id"), label="node id")
        if node_id in nodes:
            raise CmlError("duplicate node id")
        kind = _string(node.get("kind"), label="node kind")
        label = _string(node.get("label"), label="node label")
        nodes[node_id] = node
        _add_tokens(token_weights, label, NODE_WEIGHTS.get(kind, 1))
        if kind == "constraint":
            constraints.append(label)

    evidence_ids: set[str] = set()
    evidence_items = _sequence(pack.get("evidence"), label="evidence")
    for raw in evidence_items:
        item = _mapping(raw, label="evidence item")
        evidence_id = _string(item.get("id"), label="evidence id")
        if evidence_id in evidence_ids:
            raise CmlError("duplicate evidence id")
        evidence_ids.add(evidence_id)
        _add_tokens(
            token_weights,
            _string(item.get("description"), label="evidence description"),
            1,
        )

    edge_ids: set[str] = set()
    edge_pairs: set[tuple[str, str]] = set()
    for raw in raw_edges:
        edge = _mapping(raw, label="edge")
        edge_id = _string(edge.get("id"), label="edge id")
        if edge_id in edge_ids:
            raise CmlError("duplicate edge id")
        edge_ids.add(edge_id)
        source = _string(edge.get("source"), label="edge source")
        target = _string(edge.get("target"), label="edge target")
        if source == target or source not in nodes or target not in nodes:
            raise CmlError("edge must connect distinct existing nodes")
        edge_pairs.add((source, target))
        for evidence_id in _sequence(
            edge.get("evidence_ids"), label="edge evidence_ids"
        ):
            if evidence_id not in evidence_ids:
                raise CmlError("edge references missing evidence")

    selected_labels: list[str] = []
    for index, raw_id in enumerate(selected_ids):
        node_id = _string(raw_id, label="selected_path node id")
        if node_id not in nodes:
            raise CmlError("selected_path references missing node")
        selected_labels.append(_string(nodes[node_id]["label"], label="node label"))
        _add_tokens(token_weights, selected_labels[-1], 2)
        if index and (selected_ids[index - 1], node_id) not in edge_pairs:
            raise CmlError("selected_path has no directed connecting edge")
    if nodes[selected_ids[0]].get("kind") != "situation":
        raise CmlError("selected_path must start with a situation")
    if nodes[selected_ids[-1]].get("kind") not in {"outcome", "lesson"}:
        raise CmlError("selected_path must end with an outcome or lesson")

    _add_tokens(
        token_weights,
        _string(manifest.get("description"), label="manifest description"),
        2,
    )
    if visibility != "public" or contains_private_data:
        return None
    return MemoryDocument(
        source_repository=source_repository,
        registry_commit=registry_commit,
        path=path,
        pack_id=pack_id,
        source_commit=source_commit,
        situation=selected_labels[0],
        selected_path=tuple(selected_labels),
        constraints=tuple(constraints),
        token_weights=dict(sorted(token_weights.items())),
        evidence_count=len(evidence_items),
    )


def _idf(documents: Sequence[MemoryDocument]) -> dict[str, float]:
    frequencies: Counter[str] = Counter()
    for document in documents:
        frequencies.update(document.token_weights.keys())
    total = len(documents)
    return {
        token: math.log((total + 1) / (frequency + 1)) + 1.0
        for token, frequency in frequencies.items()
    }


def retrieve(
    query_weights: Mapping[str, int],
    documents: Sequence[MemoryDocument],
) -> tuple[RetrievalMatch, ...]:
    if not query_weights or not documents:
        return ()
    idf = _idf(documents)
    query_vector = {
        token: (1.0 + math.log(weight)) * idf.get(token, 1.0)
        for token, weight in query_weights.items()
        if weight > 0
    }
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    if query_norm == 0:
        return ()
    ranked: list[RetrievalMatch] = []
    for document in documents:
        vector = {
            token: (1.0 + math.log(weight)) * idf.get(token, 1.0)
            for token, weight in document.token_weights.items()
            if weight > 0
        }
        matched = sorted(set(query_vector) & set(vector))
        if len(matched) < 2:
            continue
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm == 0:
            continue
        score = sum(query_vector[token] * vector[token] for token in matched)
        score /= query_norm * norm
        if score < MIN_SCORE:
            continue
        contributions = sorted(
            matched,
            key=lambda token: (-(query_vector[token] * vector[token]), token),
        )
        ranked.append(
            RetrievalMatch(
                document=document,
                score=round(score, 6),
                matched_terms=tuple(contributions[:6]),
            )
        )
    ranked.sort(
        key=lambda item: (
            -item.score,
            -len(item.matched_terms),
            item.document.pack_id,
            item.document.path,
        )
    )
    return tuple(ranked[:MAX_RESULTS])


def _decode_content(payload: Mapping[str, Any]) -> str:
    encoded = payload.get("content")
    if payload.get("encoding") != "base64" or not isinstance(encoded, str):
        raise CmlError("memory content must use base64 encoding")
    size = payload.get("size")
    if isinstance(size, int) and size > MAX_FILE_BYTES:
        raise CmlError("memory file exceeds the safe size bound")
    try:
        raw = base64.b64decode("".join(encoded.split()), validate=True)
        if len(raw) > MAX_FILE_BYTES:
            raise CmlError("memory file exceeds the safe size bound")
        return raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise CmlError("memory content is not valid UTF-8 base64") from exc


def _source_documents(client: Any, source: Source) -> list[MemoryDocument]:
    metadata = client.get(f"/repos/{source.repository}")
    if not isinstance(metadata, dict) or metadata.get("private") is not False:
        raise CmlError("CML v0.1 source must be a public GitHub repository")
    root = quote(MEMORY_ROOT, safe="/")
    entries = client.get(
        f"/repos/{source.repository}/contents/{root}?ref={source.commit}"
    )
    if not isinstance(entries, list) or len(entries) > MAX_MEMORY_FILES:
        raise CmlError("invalid or oversized CML memory directory")
    paths: list[str] = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise CmlError("invalid CML directory entry")
        path = raw.get("path")
        if raw.get("type") != "file" or not isinstance(path, str):
            continue
        if path.startswith(f"{MEMORY_ROOT}/") and path.endswith(".json"):
            paths.append(path)
    documents: list[MemoryDocument] = []
    for path in sorted(set(paths)):
        payload = client.get(
            f"/repos/{source.repository}/contents/{quote(path, safe='/')}"
            f"?ref={source.commit}"
        )
        if not isinstance(payload, dict):
            raise CmlError("invalid CML content response")
        document = parse_memory_pack(
            _decode_content(payload),
            path=path,
            source_repository=source.repository,
            registry_commit=source.commit,
        )
        if document is not None:
            documents.append(document)
    return documents


def collect_evidence(
    *,
    registry: Registry,
    client: Any,
    target: Mapping[str, Any],
    title: str,
    filenames: Sequence[str],
) -> dict[str, Any]:
    expected_head = _full_sha(target.get("expected_head"), label="target expected head")
    base_sha = _full_sha(target.get("base_sha"), label="target base SHA")
    pr_url = _string(target.get("pr_url"), label="target PR URL")

    documents: list[MemoryDocument] = []
    source_records: list[dict[str, Any]] = []
    incomplete = False
    for source in registry.sources:
        try:
            source_documents = _source_documents(client, source)
            documents.extend(source_documents)
            source_records.append(
                {
                    "repository": source.repository,
                    "commit": source.commit,
                    "status": "PASS",
                    "publishable_candidates": len(source_documents),
                    "reason_code": None,
                }
            )
        except Exception:
            incomplete = True
            source_records.append(
                {
                    "repository": source.repository,
                    "commit": source.commit,
                    "status": "INCOMPLETE",
                    "publishable_candidates": 0,
                    "reason_code": "SOURCE_INCOMPLETE",
                }
            )

    matches = retrieve(
        build_query_weights(title=title, filenames=filenames), documents
    )
    selected = []
    for match in matches:
        document = match.document
        selected.append(
            {
                "source_repository": document.source_repository,
                "registry_commit": document.registry_commit,
                "path": document.path,
                "pack_id": document.pack_id,
                "memory_source_commit": document.source_commit,
                "score": match.score,
                "matched_terms": list(match.matched_terms),
                "situation": document.situation,
                "selected_path": list(document.selected_path),
                "constraints": list(document.constraints[:3]),
                "evidence_count": document.evidence_count,
            }
        )
    source_records.sort(key=lambda item: (item["repository"], item["commit"]))
    return {
        "schema_version": EVIDENCE_SCHEMA,
        "target": {
            "pr_url": pr_url,
            "expected_head": expected_head,
            "base_sha": base_sha,
        },
        "lane_status": "INCOMPLETE" if incomplete else "PASS",
        "sources": source_records,
        "publishable_candidates": len(documents),
        "selected": selected,
        "authority": {
            "approval": False,
            "execution": False,
            "delivery": False,
            "merge": False,
        },
    }


def scorecard_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "lane_status": evidence.get("lane_status"),
        "source_count": len(evidence.get("sources") or []),
        "publishable_candidates": evidence.get("publishable_candidates", 0),
        "selected_count": len(evidence.get("selected") or []),
        "selected": list(evidence.get("selected") or []),
        "authority": evidence.get("authority"),
    }


def _safe_markdown(value: object, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return html.escape(text.replace("`", "'"), quote=False)


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "## Causal Memory",
        "",
        f"- Lane: **{_safe_markdown(summary.get('lane_status'), 40)}**",
        f"- Trusted sources: **{int(summary.get('source_count') or 0)}**",
        f"- Publishable candidates: **{int(summary.get('publishable_candidates') or 0)}**",
        f"- Selected memories: **{int(summary.get('selected_count') or 0)}**",
        "",
    ]
    selected = summary.get("selected") or []
    if selected:
        for index, item in enumerate(selected, start=1):
            path = " → ".join(
                _safe_markdown(value, 220)
                for value in (item.get("selected_path") or [])
            )
            lines.extend(
                [
                    f"### {index}. {_safe_markdown(item.get('situation'), 240)}",
                    "",
                    f"- Relevance: `{float(item.get('score') or 0):.6f}`",
                    f"- Source: `{_safe_markdown(item.get('source_repository'), 160)}@{_safe_markdown(item.get('registry_commit'), 40)}`",
                    f"- Pack: `{_safe_markdown(item.get('pack_id'), 64)}`",
                    f"- Best-known path: {path}",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "No publishable accepted CML memory met the deterministic relevance threshold.",
                "",
            ]
        )
    lines.extend(
        [
            "CML evidence is advisory context only. It cannot approve, execute, deliver, or merge this change.",
            "",
        ]
    )
    return "\n".join(lines)
