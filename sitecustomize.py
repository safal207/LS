from pathlib import Path
import sys

root = Path(__file__).resolve().parent
python_root = root / "python"
modules_root = python_root / "modules"

# Ensure module shims resolve before the config/ directory namespace
for path in (modules_root, python_root):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
