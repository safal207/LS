from __future__ import annotations

import sys
from pathlib import Path

_modules_root = Path(__file__).resolve().parent / "python" / "modules"
if str(_modules_root) not in sys.path:
    sys.path.insert(0, str(_modules_root))

from audio.audio_module import *  # noqa: F401,F403

if __name__ == "__main__":
    test_audio_module()

