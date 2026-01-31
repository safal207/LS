import logging
from ..belief.events import BeliefEvent, BeliefDeprecatedEvent, BeliefRemovedEvent, BeliefConflictedEvent
from .state import MissionState

logger = logging.getLogger("MissionCleanup")

class MissionCleanupObserver:
    """
    Observes belief lifecycle events and cleans up MissionState accordingly.
    """
    def __init__(self, mission_state: MissionState):
        self.mission = mission_state

    def handle_event(self, event: BeliefEvent):
        if isinstance(event, (BeliefDeprecatedEvent, BeliefRemovedEvent)):
            logger.info(f"🧹 Cleanup triggered for belief: {event.belief_text}")
            self.mission.remove_convict(event.belief_text)

        elif isinstance(event, BeliefConflictedEvent):
            # Optional: could flag the belief in MissionState as disputed
            # For now, just log.
            # If the conflict resolution resulted in deprecation, a DeprecatedEvent will follow.
            pass
