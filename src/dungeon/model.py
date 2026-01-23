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

    spells: dict[Spell, int] = field(default_factory=dict)

    fatigued: bool = False
    temp_armor_bonus: int = 0

    attr_potion_target: str | None = None


@dataclass
class Encounter:
    monster_level: int
    monster_name: str
    vitality: int
