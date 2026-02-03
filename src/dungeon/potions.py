from __future__ import annotations

from dungeon.types import Event


def _attribute_outcome_text(*, target: str, change: int) -> str:
    match target:
        case "STR":
            return (
                "The potion increases your strength."
                if change >= 0
                else "The potion decreases your strength."
            )
        case "DEX":
            return (
                "The potion increases your dexterity."
                if change >= 0
                else "The potion decreases your dexterity."
            )
        case "IQ":
            return (
                "The potion makes you smarter."
                if change >= 0
                else "The potion makes you dumber."
            )
        case "MHP":
            return "Strange energies surge through you." if change >= 0 else "You feel weaker."
        case _:
            return "Strange energies surge through you."


def drink_healing_potion_events() -> list[Event]:
    return [
        Event.info("You drink the potion..."),
        Event.info("Healing results."),
    ]


def drink_attribute_potion_events(*, target: str, change: int) -> list[Event]:
    return [
        Event.info("You drink the potion..."),
        Event.info(_attribute_outcome_text(target=target, change=change)),
    ]
