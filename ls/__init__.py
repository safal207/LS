"""LS runtime helpers."""
from pathlib import Path as _Path

_python_ls = _Path(__file__).resolve().parent.parent / "python" / "ls"
if _python_ls.is_dir() and str(_python_ls) not in __path__:
    __path__.append(str(_python_ls))
