"""Root conftest — ensure module paths are available for all tests."""

import sys
from pathlib import Path

root = Path(__file__).resolve().parent

# Ensure python/modules and python are at the front of sys.path so they
# take priority over the project root (which pytest may prepend when
# tests/__init__.py exists).  Always move them to position 0 to win any
# race with pytest's own path manipulation.
for p in [root / "python" / "modules", root / "python"]:
    p_str = str(p)
    if p_str in sys.path:
        sys.path.remove(p_str)
    sys.path.insert(0, p_str)

# Also add the project root so root-level packages (agent/, codex/, etc.)
# are importable as fallback when not shadowed by python/modules.
if str(root) not in sys.path:
    sys.path.append(str(root))
