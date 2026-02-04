from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(Path(__file__).resolve().parents[1] / "apps" / "ghostgpt" / "main.py", run_name="__main__")
