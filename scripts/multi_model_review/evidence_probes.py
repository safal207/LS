"""Deterministic structural probes and safe counterexample reproductions."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class ReproductionResult:
    reproduction_id: str
    finding_ids: tuple[str, ...]
    tier: EvidenceTier
    reproduced: bool
    evidence: str
    inputs: dict[str, Any]
    observed: dict[str, Any]


_SHAPE_ERROR_MARKERS = (
    "unexpected key",
    "unexpected field",
    "unknown key",
    "unknown field",
)
_UNKNOWN_CATEGORIES = ("envelope", "event", "actor", "bindings")


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
    docstring_owners = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, docstring_owners) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            result.add(id(first.value))
    return result


def _function_scope(tree: ast.Module, function_name: str | None) -> list[ast.AST]:
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if function_name is None:
        return functions or [tree]
    return [node for node in functions if node.name == function_name]


def _names_in(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _assigned_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        result: set[str] = set()
        for item in target.elts:
            result.update(_assigned_names(item))
        return result
    return set()


def _body_has_rejection(body: list[ast.stmt]) -> bool:
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, (ast.Raise, ast.Return)):
                return True
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"append", "add"}
            ):
                strings = {
                    child.value.lower()
                    for child in ast.walk(node)
                    if isinstance(child, ast.Constant) and isinstance(child.value, str)
                }
                if any(marker in value for marker in _SHAPE_ERROR_MARKERS for value in strings):
                    return True
    return False


def _is_key_collection(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "keys"
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"set", "frozenset"}
    )


def _contains_key_guard_expression(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Sub):
            if _is_key_collection(child.left):
                return True
        if isinstance(child, ast.Compare):
            if any(isinstance(op, (ast.NotIn, ast.NotEq, ast.LtE, ast.GtE)) for op in child.ops):
                operands = [child.left, *child.comparators]
                if any(_is_key_collection(value) for value in operands):
                    return True
    return False


def _has_shape_guard(source: str, function_name: str | None = None) -> bool:
    tree = _parse_source(source)
    if tree is None:
        return False
    scopes = _function_scope(tree, function_name)
    if function_name is not None and not scopes:
        return False
    for scope in scopes:
        guard_variables: set[str] = set()
        for node in ast.walk(scope):
            if isinstance(node, ast.Assign) and _contains_key_guard_expression(node.value):
                for target in node.targets:
                    guard_variables.update(_assigned_names(target))
            elif isinstance(node, ast.AnnAssign) and node.value is not None and _contains_key_guard_expression(node.value):
                guard_variables.update(_assigned_names(node.target))
        for node in ast.walk(scope):
            if not isinstance(node, ast.If) or not _body_has_rejection(node.body):
                continue
            if _contains_key_guard_expression(node.test):
                return True
            if _names_in(node.test) & guard_variables:
                return True
    return False


def probe_unknown_property_parity(
    *,
    schema: dict[str, Any],
    schema_path: str,
    validator_source: str,
    validator_path: str,
    category: str,
    function_name: str | None,
) -> ProbeFinding | None:
    if category not in _UNKNOWN_CATEGORIES:
        raise ValueError(f"unknown closed-object category: {category}")
    if schema.get("additionalProperties") is not False:
        return None
    if _has_shape_guard(validator_source, function_name):
        return None
    return ProbeFinding(
        finding_id=f"schema-runtime-unknown-{category}-property",
        title=f"Unknown {category} properties are closed by schema but not runtime-enforced",
        tier=EvidenceTier.T1_STRUCTURAL,
        primary_artifact=validator_path,
        related_artifact=schema_path,
        violated_relation=Relation.IMPLEMENTS,
        evidence=(
            f"The {category} object declares additionalProperties=false, while "
            f"{function_name or 'the supplied runtime'} has no AST-visible rejecting key-set guard."
        ),
        counterexample_recipe={
            "category": category,
            "mutation": {f"unexpected_{category}": True},
            "expected_schema_result": "REJECT",
            "runtime_risk": "ACCEPT",
        },
    )


def probe_additional_properties_parity(
    *, schema: dict[str, Any], schema_path: str, validator_source: str, validator_path: str
) -> ProbeFinding | None:
    """Compatibility aggregate for callers that do not identify a closed-object category."""
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
        evidence=(
            "The schema closes one or more objects with additionalProperties=false, while the "
            "validator contains no AST-visible rejecting key-set guard."
        ),
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


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_anchored_pattern(pattern: str) -> bool:
    return pattern.startswith("^") and (pattern.endswith("$") or pattern.endswith(r"\Z"))


def _weak_digest_variables(tree: ast.AST) -> set[str]:
    variables: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "startswith"
            and any(_literal_string(argument) == "sha256:" for argument in node.args)
        ):
            continue
        variables.update(_names_in(node.func.value))
    return variables


def _compiled_digest_patterns(tree: ast.AST, patterns: set[str]) -> dict[str, str]:
    compiled: dict[str, str] = {}
    for node in ast.walk(tree):
        value: ast.AST | None = None
        targets: set[str] = set()
        if isinstance(node, ast.Assign):
            value = node.value
            for target in node.targets:
                targets.update(_assigned_names(target))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
            targets.update(_assigned_names(node.target))
        if not (
            targets
            and isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "re"
            and value.func.attr == "compile"
            and value.args
        ):
            continue
        pattern = _literal_string(value.args[0])
        if pattern in patterns:
            for target in targets:
                compiled[target] = pattern
    return compiled


def _strong_regex_call(
    call: ast.Call,
    patterns: set[str],
    compiled: dict[str, str],
) -> tuple[set[str], bool]:
    if not isinstance(call.func, ast.Attribute):
        return set(), False
    method = call.func.attr
    pattern: str | None = None
    value_node: ast.AST | None = None

    if isinstance(call.func.value, ast.Name) and call.func.value.id == "re":
        if method not in {"fullmatch", "match"} or len(call.args) < 2:
            return set(), False
        pattern = _literal_string(call.args[0])
        value_node = call.args[1]
    elif isinstance(call.func.value, ast.Name) and call.func.value.id in compiled:
        if method not in {"fullmatch", "match"} or not call.args:
            return set(), False
        pattern = compiled[call.func.value.id]
        value_node = call.args[0]
    elif (
        isinstance(call.func.value, ast.Call)
        and isinstance(call.func.value.func, ast.Attribute)
        and isinstance(call.func.value.func.value, ast.Name)
        and call.func.value.func.value.id == "re"
        and call.func.value.func.attr == "compile"
        and call.func.value.args
        and method in {"fullmatch", "match"}
        and call.args
    ):
        pattern = _literal_string(call.func.value.args[0])
        value_node = call.args[0]

    if pattern not in patterns or value_node is None:
        return set(), False
    if method == "match" and not _is_anchored_pattern(pattern):
        return set(), False
    return _names_in(value_node), True


def _strong_digest_variables(tree: ast.Module, patterns: set[str]) -> set[str]:
    compiled = _compiled_digest_patterns(tree, patterns)
    strong: set[str] = set()
    helper_parameters: dict[str, set[int]] = {}

    for function in (
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        parameters = [argument.arg for argument in function.args.args]
        strong_in_function: set[str] = set()
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            variables, is_strong = _strong_regex_call(call, patterns, compiled)
            if is_strong:
                strong_in_function.update(variables)
                strong.update(variables)
        indexes = {index for index, name in enumerate(parameters) if name in strong_in_function}
        if indexes:
            helper_parameters[function.name] = indexes

    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        variables, is_strong = _strong_regex_call(call, patterns, compiled)
        if is_strong:
            strong.update(variables)
        if isinstance(call.func, ast.Name) and call.func.id in helper_parameters:
            for index in helper_parameters[call.func.id]:
                if index < len(call.args):
                    strong.update(_names_in(call.args[index]))
    return strong


def probe_digest_pattern_parity(
    *, schema: dict[str, Any], schema_path: str, validator_source: str, validator_path: str
) -> ProbeFinding | None:
    patterns = _digest_patterns(schema)
    if not patterns:
        return None
    tree = _parse_source(validator_source)
    if tree is None:
        return None
    weak_variables = _weak_digest_variables(tree)
    if not weak_variables:
        return None
    strong_variables = _strong_digest_variables(tree, set(patterns))
    if weak_variables <= strong_variables:
        return None
    return ProbeFinding(
        finding_id="schema-runtime-digest-pattern-parity",
        title="Digest validation is weaker than the JSON Schema pattern",
        tier=EvidenceTier.T1_STRUCTURAL,
        primary_artifact=validator_path,
        related_artifact=schema_path,
        violated_relation=Relation.IMPLEMENTS,
        evidence=(
            f"Schema patterns {patterns!r} require a bounded digest alphabet, but prefix-only "
            f"runtime variables {sorted(weak_variables - strong_variables)!r} have no matching "
            "anchored regex enforcement."
        ),
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


def _timezone_expression_name(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "tzinfo"
        and isinstance(node.value, ast.Name)
    ):
        return node.value.id
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "utcoffset"
        and isinstance(node.func.value, ast.Name)
    ):
        return node.func.value.id
    return None


def _none_guard(compare: ast.Compare) -> tuple[str, bool] | None:
    if len(compare.ops) != 1 or len(compare.comparators) != 1:
        return None
    left, right = compare.left, compare.comparators[0]
    left_name = _timezone_expression_name(left)
    right_name = _timezone_expression_name(right)
    left_none = isinstance(left, ast.Constant) and left.value is None
    right_none = isinstance(right, ast.Constant) and right.value is None
    name = left_name if right_none else right_name if left_none else None
    if name is None:
        return None
    operator = compare.ops[0]
    if isinstance(operator, ast.Is):
        return name, True
    if isinstance(operator, ast.IsNot):
        return name, False
    return None


def _timezone_normalized_names(scope: ast.AST) -> set[str]:
    normalized: set[str] = set()
    for node in ast.walk(scope):
        value: ast.AST | None = None
        targets: set[str] = set()
        if isinstance(node, ast.Assign):
            value = node.value
            for target in node.targets:
                targets.update(_assigned_names(target))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
            targets.update(_assigned_names(node.target))
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
            continue
        if value.func.attr == "astimezone":
            normalized.update(targets)
        elif value.func.attr == "replace" and any(
            keyword.arg == "tzinfo"
            and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None)
            for keyword in value.keywords
        ):
            normalized.update(targets)
    return normalized


def _timezone_guarded_names(function: ast.AST) -> set[str]:
    guarded = _timezone_normalized_names(function)
    for node in ast.walk(function):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            guard = _none_guard(node.test)
            if guard is None:
                continue
            name, none_when_true = guard
            if none_when_true and _body_has_rejection(node.body):
                guarded.add(name)
            elif not none_when_true and _body_has_rejection(node.orelse):
                guarded.add(name)
        elif isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
            guard = _none_guard(node.test)
            if guard is not None and guard[1] is False:
                guarded.add(guard[0])
    return guarded


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
                    f"{sorted(unsafe_names)!r} without an AST-visible rejecting or normalizing guard."
                ),
                counterexample_recipe={
                    "inputs": ["2026-07-06T18:55:00", "2026-07-06T18:55:00Z"],
                    "operation": "exercise the identified comparison chain",
                    "expected_failure": "offset-naive/offset-aware comparison raises TypeError",
                },
            )
    return None


def _is_add_argument_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "add_argument"
    return isinstance(node.func, ast.Name) and node.func.id == "add_argument"


def _required_flags(argparse_source: str) -> set[str]:
    tree = _parse_source(argparse_source)
    if tree is None:
        return set()
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_add_argument_call(node):
            continue
        required = next((keyword.value for keyword in node.keywords if keyword.arg == "required"), None)
        if not isinstance(required, ast.Constant) or required.value is not True:
            continue
        for argument in node.args:
            if (
                isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
                and argument.value.startswith("--")
            ):
                flags.add(argument.value)
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


def _specimen_unknown_cases(files: dict[str, Any]) -> list[tuple[str, dict[str, Any], str | None]]:
    envelope = files["envelope.schema.json"]
    event = files["event.schema.json"]
    properties = event.get("properties", {})
    actor = properties.get("actor")
    bindings = properties.get("bindings")
    if not isinstance(envelope, dict) or not isinstance(event, dict):
        raise ValueError("specimen schemas must be objects")
    if not isinstance(actor, dict) or not isinstance(bindings, dict):
        raise ValueError("event schema must contain actor and bindings objects")
    return [
        ("envelope", envelope, "validate_envelope"),
        ("event", event, "validate_event"),
        ("actor", actor, "validate_actor"),
        ("bindings", bindings, "validate_bindings"),
    ]


def load_pattern_specimen(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("pattern specimen must be an object")
    if value.get("artifact_fidelity") != "SYNTHETIC_REPRODUCTION_SPECIMEN":
        raise ValueError("pattern specimen must declare synthetic reproduction fidelity")
    files = value.get("files")
    required_files = {
        "envelope.schema.json",
        "event.schema.json",
        "validate_v0_1.py",
        "validate_v0_2.py",
        "spec_v0_2.md",
        "coverage.txt",
    }
    if not isinstance(files, dict) or not required_files <= set(files):
        raise ValueError("pattern specimen is missing required files")
    if not isinstance(value.get("known_paths"), list):
        raise ValueError("pattern specimen known_paths must be an array")
    if not isinstance(value.get("expected_signature_ids"), list):
        raise ValueError("pattern specimen expected_signature_ids must be an array")
    if not isinstance(value.get("expected_reproduction_ids"), list):
        raise ValueError("pattern specimen expected_reproduction_ids must be an array")
    if not isinstance(value.get("reproduction_inputs"), dict):
        raise ValueError("pattern specimen reproduction_inputs must be an object")
    _specimen_unknown_cases(files)
    return value


def run_pattern_specimen(specimen: dict[str, Any]) -> list[ProbeFinding]:
    files = specimen["files"]
    validator_v01 = files["validate_v0_1.py"]
    findings: list[ProbeFinding] = []
    for category, schema, function_name in _specimen_unknown_cases(files):
        finding = probe_unknown_property_parity(
            schema=schema,
            schema_path=(
                "envelope.schema.json" if category == "envelope" else "event.schema.json"
            ),
            validator_source=validator_v01,
            validator_path="validate_v0_1.py",
            category=category,
            function_name=function_name,
        )
        if finding is not None:
            findings.append(finding)
    for finding in (
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


def _schema_accepts_unknown(schema: dict[str, Any], unknown_key: str) -> bool:
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    if unknown_key in properties:
        return True
    return schema.get("additionalProperties") is not False


def run_pattern_reproductions(specimen: dict[str, Any]) -> list[ReproductionResult]:
    """Execute safe generic counterexamples without importing candidate source code."""
    files = specimen["files"]
    inputs = specimen["reproduction_inputs"]
    validator_source = files["validate_v0_1.py"]
    finding_ids = {finding.finding_id for finding in run_pattern_specimen(specimen)}

    unknown_key = str(inputs["unknown_property_key"])
    unknown_observed: dict[str, Any] = {}
    unknown_ids: list[str] = []
    for category, schema, function_name in _specimen_unknown_cases(files):
        finding_id = f"schema-runtime-unknown-{category}-property"
        unknown_ids.append(finding_id)
        schema_accepts = _schema_accepts_unknown(schema, unknown_key)
        runtime_guard = _has_shape_guard(validator_source, function_name)
        unknown_observed[category] = {
            "schema_accepts": schema_accepts,
            "runtime_accepts": not runtime_guard,
        }
    unknown_reproduced = all(
        not result["schema_accepts"] and result["runtime_accepts"]
        for result in unknown_observed.values()
    ) and set(unknown_ids) <= finding_ids

    envelope_schema = files["envelope.schema.json"]
    digest_value = str(inputs["malformed_digest"])
    digest_patterns = _digest_patterns(envelope_schema)
    schema_digest_accepts = any(re.fullmatch(pattern, digest_value) is not None for pattern in digest_patterns)
    runtime_digest_accepts = digest_value.startswith("sha256:")

    naive_value = str(inputs["naive_timestamp"])
    aware_value = str(inputs["aware_timestamp"])
    naive = datetime.fromisoformat(naive_value.replace("Z", "+00:00"))
    aware = datetime.fromisoformat(aware_value.replace("Z", "+00:00"))
    timestamp_error: str | None = None
    try:
        _ = naive < aware
    except TypeError as exc:
        timestamp_error = type(exc).__name__

    required_flags = _required_flags(files["validate_v0_2.py"])
    commands = _code_blocks(files["spec_v0_2.md"])
    missing_flags = sorted(flag for flag in required_flags if flag not in commands)
    referenced_json = set(re.findall(r"[A-Za-z0-9_./-]+\.json", commands))
    missing_paths = sorted(path for path in referenced_json if path not in set(specimen["known_paths"]))

    uncovered_event = str(inputs["uncovered_event"])
    event_declared = uncovered_event in _event_enum(files["event.schema.json"])
    event_in_reducer = uncovered_event in validator_source
    event_covered = uncovered_event in files["coverage.txt"]

    return [
        ReproductionResult(
            reproduction_id="t0-unknown-property-parity",
            finding_ids=tuple(unknown_ids),
            tier=EvidenceTier.T0_REPRODUCTION,
            reproduced=unknown_reproduced,
            evidence=(
                "A trusted generic mutation was executed against four closed-object schema contracts "
                "and the AST-extracted runtime guard policy; candidate source was not imported."
            ),
            inputs={"unknown_property_key": unknown_key},
            observed=unknown_observed,
        ),
        ReproductionResult(
            reproduction_id="t0-digest-pattern-drift",
            finding_ids=("schema-runtime-digest-pattern-parity",),
            tier=EvidenceTier.T0_REPRODUCTION,
            reproduced=(
                runtime_digest_accepts
                and not schema_digest_accepts
                and "schema-runtime-digest-pattern-parity" in finding_ids
            ),
            evidence="The malformed digest was executed against the schema regex and the prefix-only runtime rule.",
            inputs={"value": digest_value},
            observed={
                "schema_accepts": schema_digest_accepts,
                "runtime_accepts": runtime_digest_accepts,
            },
        ),
        ReproductionResult(
            reproduction_id="t0-naive-aware-comparison",
            finding_ids=("temporal-naive-aware-comparison",),
            tier=EvidenceTier.T0_REPRODUCTION,
            reproduced=(timestamp_error == "TypeError" and "temporal-naive-aware-comparison" in finding_ids),
            evidence="Naive and aware datetime values were parsed and compared by the trusted reproduction harness.",
            inputs={"naive": naive_value, "aware": aware_value},
            observed={"exception": timestamp_error},
        ),
        ReproductionResult(
            reproduction_id="t0-cli-spec-mismatch",
            finding_ids=("cli-spec-parity",),
            tier=EvidenceTier.T0_REPRODUCTION,
            reproduced=(bool(missing_flags or missing_paths) and "cli-spec-parity" in finding_ids),
            evidence="The documented command was executed as a deterministic contract comparison against AST-parsed required flags and known paths.",
            inputs={"required_flags": sorted(required_flags)},
            observed={"missing_flags": missing_flags, "missing_paths": missing_paths},
        ),
        ReproductionResult(
            reproduction_id="t0-uncovered-ui-dismissed",
            finding_ids=(f"event-coverage-{uncovered_event}",),
            tier=EvidenceTier.T0_REPRODUCTION,
            reproduced=(
                event_declared
                and event_in_reducer
                and not event_covered
                and f"event-coverage-{uncovered_event}" in finding_ids
            ),
            evidence="The declared reducer transition was compared deterministically with the supplied coverage evidence.",
            inputs={"event": uncovered_event},
            observed={
                "declared": event_declared,
                "in_reducer": event_in_reducer,
                "covered": event_covered,
            },
        ),
    ]
