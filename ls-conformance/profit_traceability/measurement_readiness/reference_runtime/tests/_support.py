import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("attribute_runtime", ROOT / "attribute.py")
runtime = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runtime)
FIXTURE = ROOT / "fixtures" / "reference_input.json"


def load_bundle():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
