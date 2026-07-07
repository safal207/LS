from __future__ import annotations

from typing import Any

from review_benchmark_v0_2_common import (
    CHANNELS,
    COMMIT,
    LANES,
    PROVENANCE_LEVELS,
    RUN_ID,
    BenchmarkV02Error,
    digest,
    exact,
    repo_path,
    strings,
    text,
)


def validate_case(case: dict[str, Any]) -> None:
    exact(
        case,
        {
            "schema_version",
            "case_id",
            "status",
            "evidence_manifest_path",
            "evidence_sha256",
            "coordinates",
            "prompt_path",
            "lanes",
        },
        "case",
    )
    if case["schema_version"] != "ls.review_benchmark_case.v0.2":
        raise BenchmarkV02Error("unsupported case schema_version")
    text(case["case_id"], "case_id")
    if case["status"] not in {"PREPARED", "FROZEN"}:
        raise BenchmarkV02Error("case status must be PREPARED or FROZEN")
    repo_path(case["evidence_manifest_path"], "evidence_manifest_path")
    repo_path(case["prompt_path"], "prompt_path")
    if case["status"] == "PREPARED":
        if case["evidence_sha256"] is not None:
            raise BenchmarkV02Error("PREPARED case must not claim evidence_sha256")
    else:
        digest(case["evidence_sha256"], "evidence_sha256")

    coordinates = exact(
        case["coordinates"],
        {"repository", "pr_number", "base_sha", "head_sha", "changed_file_count"},
        "coordinates",
    )
    text(coordinates["repository"], "coordinates.repository")
    if not isinstance(coordinates["pr_number"], int) or isinstance(
        coordinates["pr_number"], bool
    ) or coordinates["pr_number"] < 1:
        raise BenchmarkV02Error("coordinates.pr_number must be positive")
    for field in ("base_sha", "head_sha"):
        if not isinstance(coordinates[field], str) or not COMMIT.fullmatch(
            coordinates[field]
        ):
            raise BenchmarkV02Error(f"coordinates.{field} must be a Git commit SHA")
    count = coordinates["changed_file_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise BenchmarkV02Error("coordinates.changed_file_count must be positive")

    lanes = case["lanes"]
    if not isinstance(lanes, list) or len(lanes) != 2:
        raise BenchmarkV02Error("lanes must contain FRONTIER_MODEL and LS exactly once")
    seen: set[str] = set()
    for index, lane in enumerate(lanes):
        exact(lane, {"lane", "visibility", "must_not_receive"}, f"lanes[{index}]")
        if lane["lane"] not in LANES or lane["lane"] in seen:
            raise BenchmarkV02Error(
                "lanes must contain FRONTIER_MODEL and LS exactly once"
            )
        seen.add(lane["lane"])
        if lane["visibility"] != "FROZEN_BUNDLE_ONLY":
            raise BenchmarkV02Error("lane visibility must be FROZEN_BUNDLE_ONLY")
        strings(lane["must_not_receive"], "must_not_receive", nonempty=True)


def validate_run_binding(binding: dict[str, Any], case: dict[str, Any]) -> None:
    validate_case(case)
    if case["status"] != "FROZEN":
        raise BenchmarkV02Error("run binding requires a FROZEN case")
    exact(
        binding,
        {
            "schema_version",
            "case_id",
            "lane",
            "evidence_sha256",
            "prompt_sha256",
            "run_id",
            "executor",
            "provenance",
            "nonce",
        },
        "run_binding",
    )
    if binding["schema_version"] != "ls.review_benchmark_run_binding.v0.2":
        raise BenchmarkV02Error("unsupported run binding schema_version")
    if binding["case_id"] != case["case_id"]:
        raise BenchmarkV02Error("run binding case_id does not match case")
    if binding["lane"] not in LANES:
        raise BenchmarkV02Error("run binding lane is invalid")
    if binding["evidence_sha256"] != case["evidence_sha256"]:
        raise BenchmarkV02Error("run binding is not bound to frozen evidence")
    digest(binding["prompt_sha256"], "run_binding.prompt_sha256")
    digest(binding["nonce"], "run_binding.nonce")
    if not isinstance(binding["run_id"], str) or not RUN_ID.fullmatch(
        binding["run_id"]
    ):
        raise BenchmarkV02Error("run_binding.run_id is invalid")

    executor = exact(
        binding["executor"],
        {"provider", "model", "version", "channel"},
        "run_binding.executor",
    )
    for field in ("provider", "model", "version"):
        text(executor[field], f"executor.{field}")
    if executor["channel"] not in CHANNELS:
        raise BenchmarkV02Error("executor.channel is invalid")

    provenance = exact(
        binding["provenance"],
        {"level", "issuer", "evidence"},
        "run_binding.provenance",
    )
    if provenance["level"] not in PROVENANCE_LEVELS:
        raise BenchmarkV02Error("provenance.level is invalid")
    text(provenance["issuer"], "provenance.issuer")
    strings(provenance["evidence"], "provenance.evidence", nonempty=True)
    required_channel = {
        "API_VERIFIED": "API",
        "WORKFLOW_VERIFIED": "WORKFLOW",
    }.get(provenance["level"])
    if required_channel and executor["channel"] != required_channel:
        raise BenchmarkV02Error(
            f"{provenance['level']} provenance requires {required_channel} channel"
        )
