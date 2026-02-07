from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class NarrativeEvent:
    text: str
    timestamp: str
    source_frame: Dict[str, Any]
