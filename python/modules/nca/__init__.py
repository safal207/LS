"""NCA Phase 1.5 prototype components."""

from .agent import NCAAgent
from .assembly import AgentState, AssemblyPoint
from .causal import CausalGraph
from .meta_observer import MetaObserver, MetaReport
from .multiagent import MultiAgentSystem
from .shared_causal import SharedCausalGraph
from .orientation import OrientationCenter
from .signals import CollectiveSignalBus, InternalSignal, SignalBus
from .trajectories import TrajectoryOption, TrajectoryPlanner
from .world import GridWorld

__all__ = [
    "NCAAgent",
    "AgentState",
    "AssemblyPoint",
    "CausalGraph",
    "MetaObserver",
    "MultiAgentSystem",
    "MetaReport",
    "OrientationCenter",
    "InternalSignal",
    "CollectiveSignalBus",
    "SignalBus",
    "TrajectoryOption",
    "TrajectoryPlanner",
    "SharedCausalGraph",
    "GridWorld",
]
