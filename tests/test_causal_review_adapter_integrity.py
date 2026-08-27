import copy

import pytest

from tools.causal_review_adapters import (
    AdapterError,
    adapt_external_review,
    build_noise_report,
)


def target():
    return {
        "repository": "safal207/LS",
        "pr_number": 874,
        "head_sha": "a" * 40,
        "patch_sha256": "sha256:" + "b" * 64,
    }


def qodo_bundle():
    return {
        "provider": "qodo",
        "target": target(),
        "execution": {
            "status": "COMPLETED",
            "provenance": "MATCHED",
            "details": "Qodo author and target metadata were verified.",
        },
        "threads": [
            {
                "id": "qodo-1",
                "author": {"login": "qodo-code-review"},
                "path": "tools/reviewer.py",
                "line": 10,
                "is_resolved": False,
                "is_outdated": False,
                "source_url": "https://github.example/qodo-1",
                "body": (
                    '1\\. Patch framing issue <code>Bug</code>\n'
                    '<pre>Untrusted patch content can escape its framing boundary.</pre>'
                ),
            }
        ],
        "dedupe_overrides": {},
    }


def test_override_cannot_impersonate_provider_local_namespace():
    bundle = qodo_bundle()
    bundle["dedupe_overrides"] = {"qodo-1": "external.qodo.fake-shared-key"}

    with pytest.raises(AdapterError, match="reserved external"):
        adapt_external_review(bundle)


def test_noise_report_rejects_raw_bundle_target_mismatch():
    bundle = qodo_bundle()
    review = adapt_external_review(bundle)
    different_raw_bundle = copy.deepcopy(bundle)
    different_raw_bundle["target"]["head_sha"] = "c" * 40

    with pytest.raises(AdapterError, match="bundle/review target mismatch"):
        build_noise_report([different_raw_bundle], [review])


def test_noise_report_rejects_raw_bundle_provider_mismatch():
    bundle = qodo_bundle()
    review = adapt_external_review(bundle)
    different_raw_bundle = copy.deepcopy(bundle)
    different_raw_bundle["provider"] = "coderabbit"

    with pytest.raises(AdapterError, match="bundle/review provider mismatch"):
        build_noise_report([different_raw_bundle], [review])
