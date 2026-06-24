#!/usr/bin/env python3
"""Public entrypoint for the modern-main Trusted PR Review MVP v0.2."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping


IMPLEMENTATION = Path(__file__).with_name("run_trusted_pr_review_v0_2_impl.py")


def _load_implementation() -> Any:
    spec = importlib.util.spec_from_file_location(
        "ls_trusted_pr_review_v0_2_impl",
        IMPLEMENTATION,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {IMPLEMENTATION}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _install_authorization_event_adapter(module: Any) -> None:
    original = module.stage_event

    def adapted_stage_event(
        *,
        event_id: str,
        event_type: str,
        created_at: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized = copy.deepcopy(dict(payload))
        if event_type == "AUTHORIZATION_VERIFIED":
            normalized["valid"] = (
                normalized.get("issued") is True
                and normalized.get("verified") is True
                and normalized.get("commit_before_effect_eligible") is True
                and normalized.get("execution_authorized") is False
            )
        return original(
            event_id=event_id,
            event_type=event_type,
            created_at=created_at,
            payload=normalized,
        )

    module.stage_event = adapted_stage_event


def main() -> int:
    implementation = _load_implementation()
    _install_authorization_event_adapter(implementation)
    return int(implementation.main())


if __name__ == "__main__":
    raise SystemExit(main())
