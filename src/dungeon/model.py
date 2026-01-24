from __future__ import annotations

from dataclasses import dataclass, field

from dungeon.constants import Feature, Spell


@dataclass
class Room:
    feature: Feature = Feature.EMPTY
    monster_level: int = 0
    treasure_id: int = 0
    seen: bool = False


@dataclass
class Dungeon:
    rooms: list[list[list[Room]]]


@dataclass
class Player:
    z: int
    y: int
    x: int

    str_: int
    dex: int
    iq: int
    hp: int
    mhp: int

    gold: int
    flares: int
    treasures_found: set[int] = field(default_factory=set)

    weapon_tier: int = 0
    armor_tier: int = 0
    weapon_name: str = "none"
    armor_name: str = "none"
    armor_damaged: bool = False

    spells: dict[Spell, int] = field(default_factory=dict)

    fatigued: bool = False
    temp_armor_bonus: int = 0

    attr_potion_target: str | None = None

    def apply_attribute_change(
        self,
        *,
        target: str,
        change: int,
    ) -> None:
        match target:
            case "STR":
                self.str_ = max(1, min(18, self.str_ + change))
            case "DEX":
                self.dex = max(1, min(18, self.dex + change))
            case "IQ":
                self.iq = max(1, min(18, self.iq + change))
            case "MHP":
                self.mhp = max(1, self.mhp + change)
                self.hp = max(1, min(self.hp + change, self.mhp))
