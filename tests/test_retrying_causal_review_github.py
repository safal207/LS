import io
import urllib.error

import pytest

from tools.github_causal_review_collector import CollectorError
from tools.retrying_causal_review_github import (
    RetryingGitHubApiClient,
    trigger_neutral_error,
)


class FakeResponse:
    def __init__(self, body=b"ok"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


def http_error(code, body=b"temporary"):
    return urllib.error.HTTPError(
        "https://api.github.test/resource",
        code,
        "error",
        hdrs=None,
        fp=io.BytesIO(body),
    )


def test_retryable_http_errors_use_bounded_exponential_backoff(monkeypatch):
    outcomes = [http_error(503), http_error(429), FakeResponse(b"success")]
    delays = []

    def urlopen(request, timeout):
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(
        "tools.retrying_causal_review_github.urllib.request.urlopen", urlopen
    )
    client = RetryingGitHubApiClient(
        "token",
        "https://api.github.test",
        max_attempts=4,
        base_delay_seconds=0.25,
        sleeper=delays.append,
    )

    assert client._request("https://api.github.test/resource") == b"success"
    assert delays == [0.25, 0.5]
    assert outcomes == []


def test_non_retryable_http_error_fails_on_first_attempt(monkeypatch):
    calls = 0
    delays = []

    def urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise http_error(401, b"bad credentials")

    monkeypatch.setattr(
        "tools.retrying_causal_review_github.urllib.request.urlopen", urlopen
    )
    client = RetryingGitHubApiClient(
        "token", max_attempts=4, sleeper=delays.append
    )

    with pytest.raises(CollectorError, match="HTTP 401.*after 1 attempt"):
        client._request("https://api.github.test/resource")

    assert calls == 1
    assert delays == []


def test_transport_failure_exhaustion_is_explicit(monkeypatch):
    calls = 0
    delays = []

    def urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("temporary DNS failure")

    monkeypatch.setattr(
        "tools.retrying_causal_review_github.urllib.request.urlopen", urlopen
    )
    client = RetryingGitHubApiClient(
        "token",
        max_attempts=3,
        base_delay_seconds=0.1,
        sleeper=delays.append,
    )

    with pytest.raises(
        CollectorError, match="transport failure.*after 3 attempt.*URLError"
    ):
        client._request("https://api.github.test/resource")

    assert calls == 3
    assert delays == [0.1, 0.2]


def test_retry_configuration_is_bounded():
    with pytest.raises(CollectorError, match="between 1 and 8"):
        RetryingGitHubApiClient("token", max_attempts=0)
    with pytest.raises(CollectorError, match="between 1 and 8"):
        RetryingGitHubApiClient("token", max_attempts=9)
    with pytest.raises(CollectorError, match="must not be negative"):
        RetryingGitHubApiClient("token", base_delay_seconds=-1)


def test_request_errors_use_trigger_neutral_diagnostics():
    message = trigger_neutral_error(
        RuntimeError("workflow_run head mismatch: expected a, got b")
    )
    assert message == "trigger context head mismatch: expected a, got b"
    assert "workflow_run" not in message
