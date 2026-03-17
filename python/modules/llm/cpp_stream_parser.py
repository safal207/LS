from __future__ import annotations

import ctypes
from ctypes import c_char_p, c_int, create_string_buffer, byref
from pathlib import Path
from typing import Optional

_lib = None


def _candidates() -> list[Path]:
    root = Path(__file__).resolve().parents[3]
    return [
        root / "cpp" / "build" / "libollama_stream_parser.so",
        root / "cpp" / "build" / "ollama_stream_parser.dll",
        root / "cpp" / "build" / "libollama_stream_parser.dylib",
    ]


def _load_lib() -> Optional[ctypes.CDLL]:
    global _lib
    if _lib is not None:
        return _lib

    for path in _candidates():
        if not path.exists():
            continue
        lib = ctypes.CDLL(str(path))
        lib.extract_ollama_token_cpp.argtypes = [c_char_p, c_int, c_char_p, c_int, ctypes.POINTER(c_int)]
        lib.extract_ollama_token_cpp.restype = c_int
        _lib = lib
        return _lib
    return None


def extract_ollama_token_cpp(frame_line: str, has_messages: bool) -> Optional[str]:
    lib = _load_lib()
    if lib is None:
        return None

    out = create_string_buffer(8192)
    out_len = c_int(0)
    rc = lib.extract_ollama_token_cpp(
        frame_line.encode("utf-8"),
        1 if has_messages else 0,
        out,
        len(out),
        byref(out_len),
    )
    if rc <= 0:
        return None
    return out.value.decode("utf-8", errors="ignore")
