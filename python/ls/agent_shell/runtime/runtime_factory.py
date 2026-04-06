from __future__ import annotations

from ls.agent_shell.testing.runtime_fixture import FixtureRuntime


def build_runtime() -> FixtureRuntime:
    """Temporary shell-runtime bridge.

    This keeps MCP binding contract exercised end-to-end until the
    authoritative shell runtime package is wired in after rebase.
    """

    return FixtureRuntime()
