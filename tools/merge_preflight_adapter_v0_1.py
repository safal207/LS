#!/usr/bin/env python3
"""Merge-preflight adapter over a local ReviewDecision service object."""

from __future__ import annotations

from typing import Any

import github_merge_binding_v0_1 as binding_core
import github_merge_projection_v0_1 as projection_core


def evaluate(value: Any, service: Any) -> dict[str, Any]:
    validated = None
    try:
        validated = binding_core.validate(value)
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        status, raw_response = service.project(validated["approval"], request_id)
        if status not in {200, 422}:
            raise projection_core.ProjectionError("GATEWAY_HTTP_ERROR", "unexpected local service status")
        response = projection_core.validate_response(raw_response, request_id)
        decision, reason = projection_core.classify(response, validated["approval"])
        return projection_core.envelope(validated, decision, reason, response=response)
    except binding_core.BindingError as exc:
        return projection_core.envelope(validated, "BLOCK", exc.code, detail=exc.detail)
    except projection_core.ProjectionError as exc:
        return projection_core.envelope(validated, "BLOCK", exc.code, detail=exc.detail)
    except Exception as exc:
        return projection_core.envelope(
            validated,
            "BLOCK",
            "GATEWAY_INTERNAL_FAILURE",
            detail=type(exc).__name__,
        )
