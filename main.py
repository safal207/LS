#!/usr/bin/env python3
# Deprecated entrypoint. Use apps/console/main.py instead.
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(Path(__file__).resolve().parent / "apps" / "console" / "main.py", run_name="__main__")
