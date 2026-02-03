from __future__ import annotations

import random
from dataclasses import dataclass

from dungeon.constants import (
    ARMOR_NAMES,
    ARMOR_PRICES,
    POTION_PRICES,
    SPELL_PRICES,
    WEAPON_NAMES,
    WEAPON_PRICES,
    Race,
    Spell,
)
from dungeon.model import Player
from dungeon.potions import drink_attribute_potion_events, drink_healing_potion_events
from dungeon.types import Event


@dataclass
class VendorResult:
    events: list[Event]
    done: bool = False


def _race_label(race: Race) -> str:
    match race:
        case Race.HUMAN:
            return "Human"
        case Race.DWARF:
            return "Dwarf"
        case Race.ELF:
            return "Elf"
        case Race.HALFLING:
            return "Halfling"
    return "Adventurer"


class VendorSession:
    def __init__(self, *, rng: random.Random, player: Player) -> None:
        self.rng = rng
        self.player = player
        self.phase = "category"
        self.category: str | None = None

    def start_events(self) -> list[Event]:
        return [self._category_prompt()]

    def resume_events(self) -> list[Event]:
        match self.phase:
            case "item":
                return [self._item_prompt()]
            case "attribute":
                return [self._attribute_prompt()]
            case _:
                return [self._category_prompt()]

    def prompt(self) -> str:
        return "?> "

    def step(self, raw: str) -> VendorResult:
        match self.phase:
            case "category":
                return self._handle_shop_category(raw)
            case "item":
                return self._handle_shop_item(raw)
            case "attribute":
                return self._handle_shop_attribute(raw)
            case _:
                return VendorResult(
                    events=[Event.error("Choose W/A/S/P/F or Esc."), self._category_prompt()]
                )

    def attempt_cancel(self) -> VendorResult:
        match self.phase:
            case "attribute":
                self.phase = "item"
                return VendorResult(events=[self._item_prompt()])
            case "item":
                self.phase = "category"
                self.category = None
                return VendorResult(events=[self._category_prompt()])
            case _:
                return VendorResult(events=[Event.info("Perhaps another time.")], done=True)

    def _handle_shop_category(self, raw: str) -> VendorResult:
        match raw:
            case "W" | "A" | "S" | "P":
                self.category = raw
                self.phase = "item"
                return VendorResult(events=[self._item_prompt()])
            case "F":
                return self._purchase_flares()
            case _:
                return VendorResult(
                    events=[Event.error("Choose W/A/S/P/F or Esc."), self._category_prompt()]
                )

    def _handle_shop_item(self, raw: str) -> VendorResult:
        match self.category:
            case "W":
                return self._handle_shop_weapons(raw)
            case "A":
                return self._handle_shop_armor(raw)
            case "S":
                return self._handle_shop_scrolls(raw)
            case "P":
                return self._handle_shop_potions(raw)
            case _:
                return VendorResult(
                    events=[Event.error("Choose W/A/S/P/F or Esc."), self._category_prompt()]
                )

    def _handle_shop_weapons(self, raw: str) -> VendorResult:
        tiers = {"D": 1, "S": 2, "B": 3}
        tier = tiers.get(raw)
        if tier is None:
            return VendorResult(events=[Event.error("Choose D/S/B."), self._item_prompt()])
        price = WEAPON_PRICES[tier]
        if self.player.gold < price:
            return VendorResult(events=[self._insufficient_gold_message(), self._item_prompt()])
        self.player.weapon_tier = tier
        self.player.weapon_name = WEAPON_NAMES[tier]
        self.player.weapon_broken = False
        self.player.gold -= price
        return VendorResult(events=[Event.info("A fine weapon for your quest.")], done=True)

    def _handle_shop_armor(self, raw: str) -> VendorResult:
        tiers = {"L": 1, "W": 2, "C": 3}
        tier = tiers.get(raw)
        if tier is None:
            return VendorResult(events=[Event.error("Choose L/W/C."), self._item_prompt()])
        price = ARMOR_PRICES[tier]
        if self.player.gold < price:
            return VendorResult(events=[self._insufficient_gold_message(), self._item_prompt()])
        self.player.armor_tier = tier
        self.player.armor_name = ARMOR_NAMES[tier]
        self.player.armor_damaged = False
        self.player.gold -= price
        return VendorResult(events=[Event.info("Armor fitted and ready.")], done=True)

    def _handle_shop_scrolls(self, raw: str) -> VendorResult:
        spells = {
            "P": Spell.PROTECTION,
            "F": Spell.FIREBALL,
            "L": Spell.LIGHTNING,
            "W": Spell.WEAKEN,
            "T": Spell.TELEPORT,
        }
        spell = spells.get(raw)
        if spell is None:
            return VendorResult(events=[Event.error("Choose P/F/L/W/T."), self._item_prompt()])
        price = SPELL_PRICES[spell]
        if self.player.gold < price:
            return VendorResult(events=[self._insufficient_gold_message(), self._item_prompt()])
        self.player.gold -= price
        self.player.spells[spell] = self.player.spells.get(spell, 0) + 1
        return VendorResult(events=[Event.info("A scroll is yours.")], done=True)

    def _handle_shop_potions(self, raw: str) -> VendorResult:
        match raw:
            case "H":
                price = POTION_PRICES["HEALING"]
                if self.player.gold < price:
                    return VendorResult(
                        events=[self._insufficient_gold_message(), self._item_prompt()]
                    )
                self.player.gold -= price
                self.player.hp = min(self.player.mhp, self.player.hp + 10)
                return VendorResult(events=drink_healing_potion_events(), done=True)
            case "A":
                if self.player.gold < POTION_PRICES["ATTRIBUTE"]:
                    return VendorResult(
                        events=[self._insufficient_gold_message(), self._item_prompt()]
                    )
                self.phase = "attribute"
                return VendorResult(events=[self._attribute_prompt()])
            case _:
                return VendorResult(events=[Event.error("Choose H or A."), self._item_prompt()])

    def _purchase_flares(self) -> VendorResult:
        price = 10
        if self.player.gold < price:
            return VendorResult(events=[self._insufficient_gold_message(), self._category_prompt()])
        self.player.gold -= price
        self.player.flares += 10
        return VendorResult(events=[Event.info("Ten flares, as promised.")], done=True)

    def _handle_shop_attribute(self, raw: str) -> VendorResult:
        targets = {"S": "STR", "D": "DEX", "I": "IQ", "M": "MHP"}
        target = targets.get(raw)
        if target is None:
            return VendorResult(
                events=[Event.error("Choose S/D/I/M or Esc."), self._attribute_prompt()]
            )
        price = POTION_PRICES["ATTRIBUTE"]
        if self.player.gold < price:
            return VendorResult(events=[self._insufficient_gold_message()], done=True)
        self.player.gold -= price
        change = self.rng.randint(1, 3)
        self.player.apply_attribute_change(target=target, change=change)
        return VendorResult(
            events=drink_attribute_potion_events(target=target, change=change),
            done=True,
        )

    def _insufficient_gold_message(self) -> Event:
        return Event.info(
            f"Don't try to cheat me, you foolish {_race_label(self.player.race)}. It won't work!"
        )

    def _category_prompt(self) -> Event:
        return Event.prompt(
            "He is selling:",
            options=[
                {"key": "W", "label": "Weapons", "disabled": False},
                {"key": "A", "label": "Armor", "disabled": False},
                {"key": "S", "label": "Scrolls", "disabled": False},
                {"key": "P", "label": "Potions", "disabled": False},
                {"key": "F", "label": "Flares", "disabled": self.player.gold < 10},
            ],
            has_cancel=True,
        )

    def _item_prompt(self) -> Event:
        match self.category:
            case "W":
                return Event.prompt(
                    "Choose a weapon:",
                    options=[
                        {
                            "key": "D",
                            "label": f"Dagger ({WEAPON_PRICES[1]}g)",
                            "disabled": self.player.gold < WEAPON_PRICES[1],
                        },
                        {
                            "key": "S",
                            "label": f"Short sword ({WEAPON_PRICES[2]}g)",
                            "disabled": self.player.gold < WEAPON_PRICES[2],
                        },
                        {
                            "key": "B",
                            "label": f"Broadsword ({WEAPON_PRICES[3]}g)",
                            "disabled": self.player.gold < WEAPON_PRICES[3],
                        },
                    ],
                    has_cancel=True,
                )
            case "A":
                return Event.prompt(
                    "Choose armor:",
                    options=[
                        {
                            "key": "L",
                            "label": f"Leather ({ARMOR_PRICES[1]}g)",
                            "disabled": self.player.gold < ARMOR_PRICES[1],
                        },
                        {
                            "key": "W",
                            "label": f"Wooden ({ARMOR_PRICES[2]}g)",
                            "disabled": self.player.gold < ARMOR_PRICES[2],
                        },
                        {
                            "key": "C",
                            "label": f"Chain mail ({ARMOR_PRICES[3]}g)",
                            "disabled": self.player.gold < ARMOR_PRICES[3],
                        },
                    ],
                    has_cancel=True,
                )
            case "S":
                return Event.prompt(
                    "Choose a scroll:",
                    options=[
                        {
                            "key": "P",
                            "label": f"Protection ({SPELL_PRICES[Spell.PROTECTION]}g)",
                            "disabled": self.player.gold < SPELL_PRICES[Spell.PROTECTION],
                        },
                        {
                            "key": "F",
                            "label": f"Fireball ({SPELL_PRICES[Spell.FIREBALL]}g)",
                            "disabled": self.player.gold < SPELL_PRICES[Spell.FIREBALL],
                        },
                        {
                            "key": "L",
                            "label": f"Lightning ({SPELL_PRICES[Spell.LIGHTNING]}g)",
                            "disabled": self.player.gold < SPELL_PRICES[Spell.LIGHTNING],
                        },
                        {
                            "key": "W",
                            "label": f"Weaken ({SPELL_PRICES[Spell.WEAKEN]}g)",
                            "disabled": self.player.gold < SPELL_PRICES[Spell.WEAKEN],
                        },
                        {
                            "key": "T",
                            "label": f"Teleport ({SPELL_PRICES[Spell.TELEPORT]}g)",
                            "disabled": self.player.gold < SPELL_PRICES[Spell.TELEPORT],
                        },
                    ],
                    has_cancel=True,
                )
            case _:
                return Event.prompt(
                    "Choose a potion:",
                    options=[
                        {
                            "key": "H",
                            "label": f"Healing ({POTION_PRICES['HEALING']}g)",
                            "disabled": self.player.gold < POTION_PRICES["HEALING"],
                        },
                        {
                            "key": "A",
                            "label": f"Attribute enhancer ({POTION_PRICES['ATTRIBUTE']}g)",
                            "disabled": self.player.gold < POTION_PRICES["ATTRIBUTE"],
                        },
                    ],
                    has_cancel=True,
                )

    def _attribute_prompt(self) -> Event:
        return Event.prompt(
            "Choose an attribute:",
            options=[
                {"key": "S", "label": "Strength", "disabled": False},
                {"key": "D", "label": "Dexterity", "disabled": False},
                {"key": "I", "label": "Intelligence", "disabled": False},
                {"key": "M", "label": "Max HP", "disabled": False},
            ],
            has_cancel=True,
        )
