"""NCA Phase 1.5 prototype components."""

from .agent import NCAAgent
from .assembly import AgentState, AssemblyPoint
from .autonomy_engine import AutonomyEngine
from .causal import CausalGraph
from .meta_observer import MetaObserver, MetaReport
from .meta_cognition import MetaCognitionEngine
from .identity_core import IdentityCore
from .intent_engine import IntentEngine
from .multiagent import MultiAgentSystem
from .shared_causal import SharedCausalGraph
from .orientation import OrientationCenter
from .self_model import SelfModel
from .signals import CollectiveSignalBus, InternalSignal, SignalBus
from .trajectories import TrajectoryOption, TrajectoryPlanner
from .world import GridWorld

__all__ = [
    "NCAAgent",
    "AgentState",
    "AssemblyPoint",
    "AutonomyEngine",
    "CausalGraph",
    "MetaObserver",
    "MetaCognitionEngine",
    "IdentityCore",
    "IntentEngine",
    "MultiAgentSystem",
    "MetaReport",
    "OrientationCenter",
    "SelfModel",
    "InternalSignal",
    "CollectiveSignalBus",
    "SignalBus",
    "TrajectoryOption",
    "TrajectoryPlanner",
    "SharedCausalGraph",
    "GridWorld",
]
