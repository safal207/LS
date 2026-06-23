from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..authorization import AuthorizationBundle
from ..execution import (
    DeterministicExecutionController,
    ExecutionControlDisabledError,
    ExecutionControlUnavailableError,
    ExecutionRecord,
    ProtectedAction,
)


@dataclass(frozen=True)
class CaPUConfig:
    enabled: bool = False
    actor: str = "adapter:capu"

    def __post_init__(self) -> None:
        if not self.actor:
            raise ValueError("CaPU actor must not be empty")


class CaPUExecutionAdapter:
    def __init__(
        self,
        config: Optional[CaPUConfig] = None,
        controller: Optional[DeterministicExecutionController] = None,
    ) -> None:
        self.config = config or CaPUConfig()
        self._controller = controller

    @property
    def adapter_name(self) -> str:
        return "capu"

    def run(
        self,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        *,
        now: str,
        preconditions_met: bool = True,
    ) -> ExecutionRecord:
        controller = self._require_controller()
        return controller.run(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
        )

    def recover(
        self,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        *,
        now: str,
        preconditions_met: bool = True,
    ) -> ExecutionRecord:
        controller = self._require_controller()
        return controller.recover(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
        )

    def _require_controller(self) -> DeterministicExecutionController:
        if not self.config.enabled:
            raise ExecutionControlDisabledError("CaPU adapter is disabled")
        if self._controller is None:
            raise ExecutionControlUnavailableError("CaPU controller is unavailable")
        return self._controller
