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
    Spell,
)
from dungeon.model import Player
from dungeon.types import Event


@dataclass
class VendorResult:
    events: list[Event]
    done: bool = False


class VendorSession:
    def __init__(self, *, rng: random.Random, player: Player) -> None:
        self.rng = rng
        self.player = player
        self.phase = "category"
        self.category: str | None = None

    def start_events(self) -> list[Event]:
        return [
            Event.prompt(
                "He is selling: 1> Weapons  2> Armour  3> Scrolls  4> Potions  0> Leave"
            )
        ]

    def step(self, raw: str) -> VendorResult:
        match self.phase:
            case "category":
                return self._handle_shop_category(raw)
            case "item":
                return self._handle_shop_item(raw)
            case "attribute":
                return self._handle_shop_attribute(raw)
            case _:
                return VendorResult([Event.error("Choose 1..4.")])

    def _handle_shop_category(self, raw: str) -> VendorResult:
        prompt_map = {
            "1": "Weapons: 1> Dagger  2> Short sword  3> Broadsword  0> Leave",
            "2": "Armour: 1> Leather  2> Wooden  3> Chain mail  0> Leave",
            "3": "Scrolls: 1> Protection  2> Fireball  3> Lightning  4> Weaken  5> Teleport  0> Leave",
            "4": "Potions: 1> Healing  2> Attribute enhancer  0> Leave",
        }
        match raw:
            case "0":
                return VendorResult([Event.info("Perhaps another time.")], done=True)
            case "1" | "2" | "3" | "4":
                self.category = raw
                self.phase = "item"
                return VendorResult([Event.prompt(prompt_map[raw])])
            case _:
                return VendorResult([Event.error("Choose 1..4.")])

    def _handle_shop_item(self, raw: str) -> VendorResult:
        match raw:
            case "0":
                return VendorResult([Event.info("Perhaps another time.")], done=True)
            case "1" | "2" | "3" | "4" | "5":
                return self._handle_shop_item_choice(raw)
            case _:
                return VendorResult([Event.error("Choose 1..5.")])

    def _handle_shop_item_choice(self, raw: str) -> VendorResult:
        match self.category:
            case "1":
                return self._handle_shop_weapons(raw)
            case "2":
                return self._handle_shop_armor(raw)
            case "3":
                return self._handle_shop_scrolls(raw)
            case "4":
                return self._handle_shop_potions(raw)
            case _:
                return VendorResult([Event.error("Choose 1..4.")])

    def _handle_shop_weapons(self, raw: str) -> VendorResult:
        if raw not in {"1", "2", "3"}:
            return VendorResult([Event.error("Choose 1..3.")])
        tier = int(raw)
        price = WEAPON_PRICES[tier]
        if self.player.gold < price:
            return VendorResult([Event.info("Don't try to cheat me. It won't work!")])
        self.player.weapon_tier = tier
        self.player.weapon_name = WEAPON_NAMES[tier]
        self.player.gold -= price
        return VendorResult([Event.info("A fine weapon for your quest.")], done=True)

    def _handle_shop_armor(self, raw: str) -> VendorResult:
        if raw not in {"1", "2", "3"}:
            return VendorResult([Event.error("Choose 1..3.")])
        tier = int(raw)
        price = ARMOR_PRICES[tier]
        if self.player.gold < price:
            return VendorResult([Event.info("Don't try to cheat me. It won't work!")])
        self.player.armor_tier = tier
        self.player.armor_name = ARMOR_NAMES[tier]
        self.player.armor_damaged = False
        self.player.gold -= price
        return VendorResult([Event.info("Armor fitted and ready.")], done=True)

    def _handle_shop_scrolls(self, raw: str) -> VendorResult:
        if raw not in {"1", "2", "3", "4", "5"}:
            return VendorResult([Event.error("Choose 1..5.")])
        spell = Spell(int(raw))
        price = SPELL_PRICES[spell]
        if self.player.gold < price:
            return VendorResult([Event.info("Don't try to cheat me. It won't work!")])
        self.player.gold -= price
        self.player.spells[spell] = self.player.spells.get(spell, 0) + 1
        return VendorResult([Event.info("A scroll is yours.")], done=True)

    def _handle_shop_potions(self, raw: str) -> VendorResult:
        match raw:
            case "1":
                price = POTION_PRICES["HEALING"]
                if self.player.gold < price:
                    return VendorResult(
                        [Event.info("Don't try to cheat me. It won't work!")]
                    )
                self.player.gold -= price
                self.player.hp = min(self.player.mhp, self.player.hp + 10)
                return VendorResult(
                    [Event.info("You quaff a healing potion.")], done=True
                )
            case "2":
                price = POTION_PRICES["ATTRIBUTE"]
                if self.player.gold < price:
                    return VendorResult(
                        [Event.info("Don't try to cheat me. It won't work!")]
                    )
                self.phase = "attribute"
                return VendorResult(
                    [
                        Event.prompt(
                            "Attribute enhancer: 1> Strength  2> Dexterity  3> Intelligence  4> Max HP  0> Leave"
                        )
                    ]
                )
            case _:
                return VendorResult([Event.error("Choose 1 or 2.")])

    def _handle_shop_attribute(self, raw: str) -> VendorResult:
        if raw == "0":
            return VendorResult([Event.info("Perhaps another time.")], done=True)
        if raw not in {"1", "2", "3", "4"}:
            return VendorResult([Event.error("Choose 1..4.")])
        price = POTION_PRICES["ATTRIBUTE"]
        if self.player.gold < price:
            return VendorResult(
                [Event.info("Don't try to cheat me. It won't work!")], done=True
            )
        self.player.gold -= price
        change = self.rng.randint(1, 6)
        targets = {"1": "STR", "2": "DEX", "3": "IQ", "4": "MHP"}
        self.player.apply_attribute_change(
            target=targets[raw],
            change=change,
        )
        return VendorResult([Event.info("The potion takes effect.")], done=True)
