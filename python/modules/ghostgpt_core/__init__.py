"""Top-level modules package.

This package intentionally avoids eager imports of all subpackages.
Historically, importing ``modules`` pulled in AgentLoop and other heavy
components with optional dependencies (e.g. ``codex`` extras), which caused
unrelated scripts like Web4 load tests to fail at import time.

Import concrete submodules directly, for example:
- ``from modules.web4_runtime.loadtest import run_load_test``
- ``from modules.agent.loop import AgentLoop``
"""

__all__: list[str] = []
