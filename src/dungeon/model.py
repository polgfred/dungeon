from __future__ import annotations

from dataclasses import dataclass, field

from dungeon.constants import Feature, Race, Spell


def create_spell_counts() -> dict[Spell, int]:
    return {spell: 0 for spell in Spell}


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

    race: Race

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
    weapon_broken: bool = False
    armor_name: str = "none"
    armor_damaged: bool = False

    spells: dict[Spell, int] = field(default_factory=create_spell_counts)

    fatigued: bool = False
    temp_armor_bonus: int = 0

    @staticmethod
    def roll_base_stats(rng, race: Race) -> tuple[int, int, int, int]:
        rn = rng.randint(0, 4)
        rd = rng.randint(0, 4)
        ra = rng.randint(0, 4)
        r2 = rng.randint(0, 6)

        match race:
            case Race.HUMAN:
                return 8 + rn, 8 + rd, 8 + ra, 20 + r2
            case Race.DWARF:
                return 10 + rn, 8 + rd, 6 + ra, 22 + r2
            case Race.ELF:
                return 6 + rn, 9 + rd, 10 + ra, 16 + r2
            case Race.HALFLING:
                return 6 + rn, 10 + rd, 9 + ra, 18 + r2
            case _:
                raise ValueError("Unknown race")

    @classmethod
    def create(
        cls,
        *,
        rng,
        race: Race,
        allocations: dict[str, int],
        weapon_tier: int,
        armor_tier: int,
        flare_count: int,
    ) -> "Player":
        from dungeon.constants import (
            ARMOR_NAMES,
            ARMOR_PRICES,
            WEAPON_NAMES,
            WEAPON_PRICES,
        )

        str_, dex, iq, hp = cls.roll_base_stats(rng, race)

        str_add = int(allocations["STR"])
        dex_add = int(allocations["DEX"])
        iq_add = int(allocations["IQ"])
        if min(str_add, dex_add, iq_add) < 0:
            raise ValueError("Invalid allocation amount.")
        if str_add + dex_add + iq_add != 5:
            raise ValueError("Allocation must total 5 points.")
        str_ = min(18, str_ + str_add)
        dex = min(18, dex + dex_add)
        iq = min(18, iq + iq_add)

        gold = rng.randint(50, 60)
        if weapon_tier not in (1, 2, 3):
            raise ValueError("Weapon tier must be 1..3")
        if armor_tier not in (1, 2, 3):
            raise ValueError("Armor tier must be 1..3")
        if flare_count < 0:
            raise ValueError("Flare count must be non-negative")

        cost = WEAPON_PRICES[weapon_tier] + ARMOR_PRICES[armor_tier] + flare_count
        if cost > gold:
            raise ValueError("Not enough gold for purchases")

        return cls(
            z=0,
            y=3,
            x=3,
            race=race,
            str_=str_,
            dex=dex,
            iq=iq,
            hp=hp,
            mhp=hp,
            gold=gold - cost,
            flares=flare_count,
            weapon_tier=weapon_tier,
            armor_tier=armor_tier,
            weapon_name=WEAPON_NAMES[weapon_tier],
            weapon_broken=False,
            armor_name=ARMOR_NAMES[armor_tier],
            armor_damaged=False,
            spells=create_spell_counts(),
        )

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
