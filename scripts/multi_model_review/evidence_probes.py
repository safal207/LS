"""Deterministic structural probes for cross-artifact review evidence."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from .evidence_graph import EvidenceTier, Relation


@dataclass(frozen=True)
class ProbeFinding:
    finding_id: str
    title: str
    tier: EvidenceTier
    primary_artifact: str
    related_artifact: str
    violated_relation: Relation
    evidence: str
    counterexample_recipe: dict[str, Any] | None
    severity: str = "high"


_SHAPE_ERROR_MARKERS = (
    "unexpected key",
    "unexpected field",
    "unknown key",
    "unknown field",
)


def _iter_schema_nodes(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_schema_nodes(child)


def _schema_has_closed_objects(schema: dict[str, Any]) -> bool:
    return any(node.get("additionalProperties") is False for node in _iter_schema_nodes(schema))


def _parse_source(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    result: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            result.add(id(first.value))
    return result


def _executable_string_values(tree: ast.AST) -> set[str]:
    docstrings = _docstring_constant_ids(tree)
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def _call_attribute(node: ast.AST, attribute: str) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == attribute
        for child in ast.walk(node)
    )


def _has_shape_guard(source: str) -> bool:
    tree = _parse_source(source)
    if tree is None:
        return False
    strings = {value.lower() for value in _executable_string_values(tree)}
    identifiers = {
        token.lower()
        for node in ast.walk(tree)
        for token in (
            [node.id] if isinstance(node, ast.Name) else [node.attr] if isinstance(node, ast.Attribute) else []
        )
    }
    if "additionalproperties" in identifiers or any("additionalproperties" in value for value in strings):
        return True
    if any(marker in value for marker in _SHAPE_ERROR_MARKERS for value in strings):
        return True
    return any(
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Sub)
        and _call_attribute(node.left, "keys")
        for node in ast.walk(tree)
    )


def probe_additional_properties_parity(
    *, schema: dict[str, Any], schema_path: str, validator_source: str, validator_path: str
) -> ProbeFinding | None:
    if not _schema_has_closed_objects(schema):
        return None
    if _has_shape_guard(validator_source):
        return None
    return ProbeFinding(
        finding_id="schema-runtime-additional-properties-parity",
        title="Closed JSON objects are not enforced by the handwritten validator",
        tier=EvidenceTier.T1_STRUCTURAL,
        primary_artifact=validator_path,
        related_artifact=schema_path,
        violated_relation=Relation.IMPLEMENTS,
        evidence="The schema closes one or more objects with additionalProperties=false, while the validator contains no AST-visible unknown-key or exact-key-set guard.",
        counterexample_recipe={
            "mutation": "add an unknown property to a closed object",
            "expected_schema_result": "REJECT",
            "runtime_risk": "ACCEPT",
        },
    )


def _digest_patterns(schema: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for node in _iter_schema_nodes(schema):
        properties = node.get("properties")
        if not isinstance(properties, dict):
            continue
        for name, value in properties.items():
            if not isinstance(value, dict):
                continue
            pattern = value.get("pattern")
            if "digest" in name.lower() and isinstance(pattern, str):
                result.append(pattern)
    return sorted(set(result))


def _has_sha256_prefix_check(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "startswith"
        and any(isinstance(arg, ast.Constant) and arg.value == "sha256:" for arg in node.args)
        for node in ast.walk(tree)
    )


def _has_strong_digest_check(tree: ast.AST, patterns: Iterable[str]) -> bool:
    if _call_attribute(tree, "fullmatch"):
        return True
    executable_strings = _executable_string_values(tree)
    return any(pattern in executable_strings for pattern in patterns)


def probe_digest_pattern_parity(
    *, schema: dict[str, Any], schema_path: str, validator_source: str, validator_path: str
) -> ProbeFinding | None:
    patterns = _digest_patterns(schema)
    if not patterns:
        return None
    tree = _parse_source(validator_source)
    if tree is None:
        return None
    weak_prefix = _has_sha256_prefix_check(tree)
    strong_pattern = _has_strong_digest_check(tree, patterns)
    if not weak_prefix or strong_pattern:
        return None
    return ProbeFinding(
        finding_id="schema-runtime-digest-pattern-parity",
        title="Digest validation is weaker than the JSON Schema pattern",
        tier=EvidenceTier.T1_STRUCTURAL,
        primary_artifact=validator_path,
        related_artifact=schema_path,
        violated_relation=Relation.IMPLEMENTS,
        evidence=f"Schema patterns {patterns!r} require a bounded digest alphabet, but runtime validation only performs an AST-visible sha256: prefix check.",
        counterexample_recipe={
            "mutation": "sha256:bad value!",
            "expected_schema_result": "REJECT",
            "runtime_risk": "ACCEPT",
        },
    )


def _contains_fromisoformat(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "fromisoformat"
        for child in ast.walk(node)
    )


def _timezone_guarded_names(function: ast.AST) -> set[str]:
    guarded: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Attribute) or node.attr not in {"tzinfo", "utcoffset", "astimezone"}:
            continue
        if isinstance(node.value, ast.Name):
            guarded.add(node.value.id)
    return guarded


def _assigned_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        result: set[str] = set()
        for item in target.elts:
            result.update(_assigned_names(item))
        return result
    return set()


def _fromisoformat_assigned_names(function: ast.AST) -> set[str]:
    assigned: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and _contains_fromisoformat(node.value):
            for target in node.targets:
                assigned.update(_assigned_names(target))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and _contains_fromisoformat(node.value):
            assigned.update(_assigned_names(node.target))
        elif isinstance(node, ast.NamedExpr) and _contains_fromisoformat(node.value):
            assigned.update(_assigned_names(node.target))
    return assigned


def _names_in(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _calls_any(node: ast.AST, names: set[str]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id in names:
            return True
    return False


def _risky_timestamp_helpers(tree: ast.Module) -> set[str]:
    result: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _contains_fromisoformat(node):
            continue
        parsed_names = _fromisoformat_assigned_names(node)
        guarded_names = _timezone_guarded_names(node)
        if not parsed_names or parsed_names - guarded_names:
            result.add(node.name)
    return result


def _function_risky_variables(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    risky_helpers: set[str],
) -> set[str]:
    assignments: list[tuple[set[str], ast.AST]] = []
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            targets: set[str] = set()
            for target in node.targets:
                targets.update(_assigned_names(target))
            assignments.append((targets, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            assignments.append((_assigned_names(node.target), node.value))

    risky: set[str] = set()
    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            if not targets or targets <= risky:
                continue
            value_is_risky = (
                _contains_fromisoformat(value)
                or _calls_any(value, risky_helpers)
                or bool(_names_in(value) & risky)
            )
            if value_is_risky:
                before = len(risky)
                risky.update(targets)
                changed = changed or len(risky) != before
    return risky


def probe_timezone_comparison_safety(*, source: str, path: str) -> ProbeFinding | None:
    tree = _parse_source(source)
    if tree is None:
        return None

    risky_helpers = _risky_timestamp_helpers(tree)
    functions = (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    for function in functions:
        risky_variables = _function_risky_variables(function, risky_helpers)
        if not risky_variables:
            continue
        guarded_names = _timezone_guarded_names(function)
        for node in ast.walk(function):
            if not isinstance(node, ast.Compare):
                continue
            if not any(isinstance(op, (ast.Gt, ast.GtE, ast.Lt, ast.LtE)) for op in node.ops):
                continue
            unsafe_names = (_names_in(node) & risky_variables) - guarded_names
            if not unsafe_names:
                continue
            return ProbeFinding(
                finding_id="temporal-naive-aware-comparison",
                title="Timestamp comparison can mix naive and aware datetimes",
                tier=EvidenceTier.T1_STRUCTURAL,
                primary_artifact=path,
                related_artifact=path,
                violated_relation=Relation.OBSERVES,
                evidence=(
                    f"Function {function.name} compares timestamp-derived variable(s) "
                    f"{sorted(unsafe_names)!r} without an AST-visible guard on those variables."
                ),
                counterexample_recipe={
                    "inputs": ["2026-07-06T18:55:00", "2026-07-06T18:55:00Z"],
                    "operation": "exercise the identified comparison chain",
                    "expected_failure": "offset-naive/offset-aware comparison is rejected or raises TypeError",
                },
            )
    return None


def _required_flags(argparse_source: str) -> set[str]:
    flags: set[str] = set()
    for match in re.finditer(
        r"add_argument\(\s*[\"'](--[a-z0-9-]+)[\"'][^\)]*required\s*=\s*True",
        argparse_source,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        flags.add(match.group(1))
    return flags


def _code_blocks(markdown: str) -> str:
    return "\n".join(re.findall(r"```(?:bash|sh|shell)?\s*(.*?)```", markdown, flags=re.IGNORECASE | re.DOTALL))


def probe_cli_documentation_parity(
    *,
    argparse_source: str,
    validator_path: str,
    markdown: str,
    spec_path: str,
    known_paths: Iterable[str],
) -> ProbeFinding | None:
    commands = _code_blocks(markdown)
    required_flags = _required_flags(argparse_source)
    missing_flags = sorted(flag for flag in required_flags if flag not in commands)
    referenced_json = set(re.findall(r"[A-Za-z0-9_./-]+\.json", commands))
    known = set(known_paths)
    missing_paths = sorted(path for path in referenced_json if path not in known)
    if not missing_flags and not missing_paths:
        return None
    return ProbeFinding(
        finding_id="cli-spec-parity",
        title="Specification command diverges from the executable CLI",
        tier=EvidenceTier.T1_STRUCTURAL,
        primary_artifact=spec_path,
        related_artifact=validator_path,
        violated_relation=Relation.DOCUMENTS,
        evidence=f"Missing required flags: {missing_flags}; referenced paths absent from the review unit: {missing_paths}.",
        counterexample_recipe={
            "required_flags": sorted(required_flags),
            "missing_flags": missing_flags,
            "missing_paths": missing_paths,
        },
        severity="medium",
    )


def _event_enum(schema: dict[str, Any]) -> set[str]:
    return set(schema.get("properties", {}).get("event_type", {}).get("enum", []))


def probe_event_fixture_coverage(
    *,
    event_schema: dict[str, Any],
    schema_path: str,
    reducer_source: str,
    reducer_path: str,
    fixture_and_test_texts: Iterable[str],
) -> list[ProbeFinding]:
    coverage_text = "\n".join(fixture_and_test_texts)
    findings: list[ProbeFinding] = []
    for event in sorted(_event_enum(event_schema)):
        if event in reducer_source and event not in coverage_text:
            findings.append(
                ProbeFinding(
                    finding_id=f"event-coverage-{event}",
                    title=f"Declared transition {event} has no normative fixture coverage",
                    tier=EvidenceTier.T1_STRUCTURAL,
                    primary_artifact=reducer_path,
                    related_artifact=schema_path,
                    violated_relation=Relation.TESTS,
                    evidence=f"{event} is declared and mentioned by the reducer specimen but is absent from the supplied fixture and test evidence.",
                    counterexample_recipe={"event": event, "coverage": "ABSENT"},
                    severity="medium",
                )
            )
    return findings


def load_pattern_specimen(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("pattern specimen must be an object")
    if value.get("artifact_fidelity") != "SYNTHETIC_PATTERN_SPECIMEN":
        raise ValueError("pattern specimen must declare synthetic artifact fidelity")
    return value


def run_pattern_specimen(specimen: dict[str, Any]) -> list[ProbeFinding]:
    files = specimen["files"]
    validator_v01 = files["validate_v0_1.py"]
    findings: list[ProbeFinding] = []
    for finding in (
        probe_additional_properties_parity(
            schema=files["envelope.schema.json"],
            schema_path="envelope.schema.json",
            validator_source=validator_v01,
            validator_path="validate_v0_1.py",
        ),
        probe_digest_pattern_parity(
            schema=files["envelope.schema.json"],
            schema_path="envelope.schema.json",
            validator_source=validator_v01,
            validator_path="validate_v0_1.py",
        ),
        probe_timezone_comparison_safety(source=validator_v01, path="validate_v0_1.py"),
        probe_cli_documentation_parity(
            argparse_source=files["validate_v0_2.py"],
            validator_path="validate_v0_2.py",
            markdown=files["spec_v0_2.md"],
            spec_path="spec_v0_2.md",
            known_paths=specimen["known_paths"],
        ),
    ):
        if finding is not None:
            findings.append(finding)
    findings.extend(
        probe_event_fixture_coverage(
            event_schema=files["event.schema.json"],
            schema_path="event.schema.json",
            reducer_source=validator_v01,
            reducer_path="validate_v0_1.py",
            fixture_and_test_texts=[files["coverage.txt"]],
        )
    )
    return findings
