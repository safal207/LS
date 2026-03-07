"""Compatibility shim for legacy `import config` usage.

Prefer `from modules import config` in new code.
"""

from modules.config import *  # noqa: F401,F403
