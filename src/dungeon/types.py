from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dungeon.constants import Mode


@dataclass
class Event:
    kind: str
    text: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    events: list[Event]
    mode: Mode
    needs_input: bool
