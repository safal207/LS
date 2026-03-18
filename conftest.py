"""Root conftest — ensure module paths are available for all tests."""

import sys
from pathlib import Path

root = Path(__file__).resolve().parent
for p in [root / "python" / "modules", root / "python"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
