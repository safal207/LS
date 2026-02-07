from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LTPState = Literal["untrusted", "probing", "trusted", "quarantined"]


@dataclass
class LTPProfile:
    state: LTPState = "untrusted"

    def promote(self) -> None:
        if self.state == "untrusted":
            self.state = "probing"
        elif self.state == "probing":
            self.state = "trusted"

    def demote(self) -> None:
        if self.state == "trusted":
            self.state = "probing"
        elif self.state == "probing":
            self.state = "untrusted"

    def quarantine(self) -> None:
        self.state = "quarantined"

    def reset(self) -> None:
        self.state = "untrusted"
