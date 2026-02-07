from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class InnerAgent:
    name: str

    def process(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
