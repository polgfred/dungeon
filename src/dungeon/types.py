from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dungeon.constants import Mode


@dataclass
class Event:
    kind: str
    text: str
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def info(cls, text: str) -> "Event":
        return cls("INFO", text)

    @classmethod
    def error(cls, text: str) -> "Event":
        return cls("ERROR", text)

    @classmethod
    def combat(cls, text: str) -> "Event":
        return cls("COMBAT", text)

    @classmethod
    def loot(cls, text: str) -> "Event":
        return cls("LOOT", text)

    @classmethod
    def prompt(cls, text: str, *, data: dict[str, Any] | None = None) -> "Event":
        return cls("PROMPT", text, data or {})

    @classmethod
    def status(cls, data: dict[str, Any]) -> "Event":
        return cls("STATUS", "", data)

    @classmethod
    def map(cls, grid: list[str]) -> "Event":
        return cls("MAP", "", {"grid": grid})

    @classmethod
    def debug(cls, text: str) -> "Event":
        return cls("DEBUG", text)


@dataclass
class StepResult:
    events: list[Event]
    mode: Mode
    needs_input: bool
