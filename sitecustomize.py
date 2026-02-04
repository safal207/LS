from pathlib import Path
import sys

root = Path(__file__).resolve().parent
python_root = root / "python"
modules_root = python_root / "modules"

# Ensure module shims resolve before the config/ directory namespace
for path in (modules_root, python_root):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Provide "modules.*" namespace compatibility if used in tooling/docs.
if "modules" not in sys.modules:
    import types

    pkg = types.ModuleType("modules")
    pkg.__path__ = [str(modules_root)]
    sys.modules["modules"] = pkg
