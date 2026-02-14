"""NCA Phase 1 prototype components.

This package contains a minimal implementation of the NCA architecture:
orientation center, assembly point, meta-observer, trajectory planner,
a toy world model, and a composed single-agent runtime.
"""

from .agent import NCAAgent
from .assembly import AgentState, AssemblyPoint
from .meta_observer import MetaObserver
from .orientation import OrientationCenter
from .trajectories import TrajectoryOption, TrajectoryPlanner
from .world import GridWorld

__all__ = [
    "NCAAgent",
    "AgentState",
    "AssemblyPoint",
    "MetaObserver",
    "OrientationCenter",
    "TrajectoryOption",
    "TrajectoryPlanner",
    "GridWorld",
]
