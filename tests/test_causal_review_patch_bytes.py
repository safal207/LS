import hashlib

import pytest

from tools.causal_review import ContractError
from tools.grok_causal_review import read_bound_patch


def test_bound_patch_rejects_non_utf8_bytes(tmp_path, monkeypatch):
    patch_path = tmp_path / "review.patch"
    raw = b"diff --git a/file b/file\n+\xff\xfe"
    patch_path.write_bytes(raw)

    monkeypatch.setenv("TARGET_REPOSITORY", "safal207/example")
    monkeypatch.setenv("TARGET_PR_NUMBER", "57")
    monkeypatch.setenv("TARGET_HEAD_SHA", "a" * 40)
    monkeypatch.setenv(
        "TARGET_PATCH_SHA256",
        "sha256:" + hashlib.sha256(raw).hexdigest(),
    )

    with pytest.raises(ContractError, match="must be valid UTF-8"):
        read_bound_patch(patch_path, 1000)
