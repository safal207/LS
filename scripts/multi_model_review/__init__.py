"""Public API for the LS multi-model review runtime."""
from .aggregate import aggregate_reviews, findings_overlap, policy_decision
from .contracts import (
    ReviewRuntimeError,
    bind_provider_routes,
    changed_files_from_diff,
    classify_risk,
    extract_json_object,
    load_config,
    load_provider_config,
    redact_diff,
    validate_review_payload,
    validate_sha,
)
from .provider import (
    CatalogModel,
    OpenRouterClient,
    ResolvedModel,
    ReviewProviderClient,
    build_provider_client,
    model_is_active,
    resolve_models,
)
from .runtime import build_prompts, render_markdown, run_review, write_outputs

__all__ = [
    "CatalogModel",
    "OpenRouterClient",
    "ResolvedModel",
    "ReviewProviderClient",
    "ReviewRuntimeError",
    "aggregate_reviews",
    "bind_provider_routes",
    "build_prompts",
    "build_provider_client",
    "changed_files_from_diff",
    "classify_risk",
    "extract_json_object",
    "findings_overlap",
    "load_config",
    "load_provider_config",
    "model_is_active",
    "policy_decision",
    "redact_diff",
    "render_markdown",
    "resolve_models",
    "run_review",
    "validate_review_payload",
    "validate_sha",
    "write_outputs",
]
