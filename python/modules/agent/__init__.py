from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

from .counterfactual_engine import CounterfactualEngine
from .events import AgentEvent, EventType
from .relational_policy_engine import evaluate_relational_policy
from .sinks import EventSink, NullSink, PrintSink, build_event_sink

try:  # optional dependency chain: loop -> lthread -> cryptography
    from .loop import AgentLoop
except Exception:  # pragma: no cover - import guard for lightweight environments
    AgentLoop = None  # type: ignore[assignment]

__all__ = [
    "CounterfactualEngine",
    "AgentEvent",
    "EventType",
    "AgentLoop",
    "EventSink",
    "NullSink",
    "PrintSink",
    "build_event_sink",
    "evaluate_relational_policy",
]
