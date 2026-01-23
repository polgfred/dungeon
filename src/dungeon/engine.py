from __future__ import annotations

import random
from dataclasses import dataclass

from dungeon.constants import (
    ARMOR_NAMES,
    ARMOR_PRICES,
    ENCOUNTER_COMMANDS,
    EXPLORE_COMMANDS,
    FEATURE_SYMBOLS,
    MONSTER_NAMES,
    POTION_PRICES,
    SPELL_PRICES,
    TREASURE_NAMES,
    WEAPON_NAMES,
    WEAPON_PRICES,
    Feature,
    Mode,
    Race,
    Spell,
)
from dungeon.generation import generate_dungeon
from dungeon.model import Dungeon, Encounter, Player
from dungeon.types import Event, StepResult


@dataclass
class _ShopState:
    phase: str
    category: str | None = None
    awaiting_attribute: bool = False


def roll_base_stats(rng: random.Random, race: Race) -> tuple[int, int, int, int]:
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


def create_player(
    rng: random.Random,
    race: Race,
    allocations: dict[str, int],
    weapon_tier: int,
    armor_tier: int,
    flare_count: int,
) -> Player:
    str_, dex, iq, hp = roll_base_stats(rng, race)

    remaining = 5
    for key in ("STR", "DEX", "IQ"):
        add = int(allocations.get(key, 0))
        if add < 0 or add > remaining:
            raise ValueError("Invalid allocation amount.")
        remaining -= add
        if key == "STR":
            str_ = min(18, str_ + add)
        elif key == "DEX":
            dex = min(18, dex + add)
        elif key == "IQ":
            iq = min(18, iq + add)

    if remaining != 0:
        raise ValueError("Allocation must total 5 points.")

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

    spells = {spell: 0 for spell in Spell}

    return Player(
        z=0,
        y=3,
        x=3,
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
        armor_name=ARMOR_NAMES[armor_tier],
        spells=spells,
    )


class Game:
    def __init__(self, seed: int, player: Player, rng: random.Random | None = None):
        self.rng = rng or random.Random(seed)
        self.dungeon: Dungeon = generate_dungeon(self.rng)
        self.player = player
        self.mode = Mode.EXPLORE
        self.encounter: Encounter | None = None
        self._awaiting_spell = False
        self._shop_state: _ShopState | None = None

    def start_events(self) -> list[Event]:
        return self._enter_room()

    def step(self, command: str) -> StepResult:
        events: list[Event] = []
        raw = command.strip().upper()
        if not raw:
            return StepResult(
                events=[Event("ERROR", "I don't understand that.")],
                mode=self.mode,
                needs_input=True,
            )

        if self.mode in {Mode.GAME_OVER, Mode.VICTORY}:
            return StepResult(events=[], mode=self.mode, needs_input=False)

        if self._shop_state is not None:
            events.extend(self._handle_shop(raw))
            return StepResult(events=events, mode=self.mode, needs_input=True)

        if self._awaiting_spell:
            events.extend(self._handle_spell_choice(raw))
            return StepResult(events=events, mode=self.mode, needs_input=True)

        key = raw[0]

        if self.mode == Mode.EXPLORE:
            if key not in EXPLORE_COMMANDS:
                return StepResult(
                    events=[Event("ERROR", "I don't understand that.")],
                    mode=self.mode,
                    needs_input=True,
                )
            events.extend(self._handle_explore(key))
        elif self.mode == Mode.ENCOUNTER:
            if key not in ENCOUNTER_COMMANDS:
                return StepResult(
                    events=[Event("ERROR", "I don't understand that.")],
                    mode=self.mode,
                    needs_input=True,
                )
            events.extend(self._handle_encounter(key))

        return StepResult(events=events, mode=self.mode, needs_input=True)

    def _current_room(self):
        return self.dungeon.rooms[self.player.z][self.player.y][self.player.x]

    def _handle_explore(self, key: str) -> list[Event]:
        events: list[Event] = []
        if key == "N":
            events.extend(self._move(-1, 0))
        elif key == "S":
            events.extend(self._move(1, 0))
        elif key == "E":
            events.extend(self._move(0, 1))
        elif key == "W":
            events.extend(self._move(0, -1))
        elif key == "U":
            events.extend(self._stairs(up=True))
        elif key == "D":
            events.extend(self._stairs(up=False))
        elif key == "M":
            events.append(Event("MAP", "", data={"grid": self._map_grid()}))
        elif key == "F":
            events.extend(self._use_flare())
        elif key == "X":
            events.extend(self._attempt_exit())
        elif key == "L":
            events.extend(self._use_mirror())
        elif key == "O":
            events.extend(self._open_chest())
        elif key == "R":
            events.extend(self._read_scroll())
        elif key == "P":
            events.extend(self._drink_potion())
        elif key == "B":
            events.extend(self._open_vendor())
        elif key == "T":
            events.append(Event("STATUS", "", data=self._status_data()))
        elif key == "H":
            events.append(Event("INFO", self._help_text()))
        return events

    def _handle_encounter(self, key: str) -> list[Event]:
        if self.encounter is None:
            self.mode = Mode.EXPLORE
            return [Event("ERROR", "There is nothing to fight.")]
        if key == "F":
            return self._fight_round()
        if key == "R":
            return self._run_attempt()
        if key == "S":
            self._awaiting_spell = True
            return [Event("PROMPT", "Choose a spell:", data=self._spell_menu())]
        return []

    def _move(self, dy: int, dx: int) -> list[Event]:
        ny = self.player.y + dy
        nx = self.player.x + dx
        if ny < 0 or ny > 6 or nx < 0 or nx > 6:
            return [Event("INFO", "A wall interposes itself.")]
        self.player.y = ny
        self.player.x = nx
        return self._enter_room()

    def _stairs(self, *, up: bool) -> list[Event]:
        room = self._current_room()
        if up:
            if room.feature != Feature.STAIRS_UP:
                return [
                    Event(
                        "INFO",
                        "There are no stairs leading up here, foolish adventurer.",
                    )
                ]
            self.player.z += 1
            return self._enter_room()
        if room.feature != Feature.STAIRS_DOWN:
            return [Event("INFO", "There is no downward staircase here.")]
        self.player.z -= 1
        return self._enter_room()

    def _enter_room(self) -> list[Event]:
        events: list[Event] = []
        room = self._current_room()
        room.seen = True

        if room.monster_level > 0:
            self._start_encounter(room.monster_level)
            events.append(
                Event(
                    "COMBAT",
                    f"You are facing an angry {self.encounter.monster_name}!",
                )
            )
            self.mode = Mode.ENCOUNTER
            return events

        if room.treasure_id:
            events.extend(self._award_treasure(room.treasure_id))
            room.treasure_id = 0

        if room.feature == Feature.MIRROR:
            events.append(
                Event("INFO", "There is a magic mirror mounted on the wall here.")
            )
        elif room.feature == Feature.SCROLL:
            events.append(Event("INFO", "There is a spell scroll here."))
        elif room.feature == Feature.CHEST:
            events.append(Event("INFO", "There is a chest here."))
        elif room.feature == Feature.FLARES:
            gained = self.rng.randint(1, 5)
            self.player.flares += gained
            room.feature = Feature.EMPTY
            events.append(Event("INFO", f"You pick up {gained} flares."))
        elif room.feature == Feature.POTION:
            events.append(Event("INFO", "There is a magic potion here."))
        elif room.feature == Feature.VENDOR:
            events.append(Event("INFO", "There is a vendor here."))
        elif room.feature == Feature.THIEF:
            stolen = min(self.rng.randint(1, 50), self.player.gold)
            self.player.gold -= stolen
            room.feature = Feature.EMPTY
            events.append(Event("INFO", f"A thief steals {stolen} gold pieces."))
        elif room.feature == Feature.WARP:
            events.append(
                Event("INFO", "This room contains a warp. You are whisked elsewhere...")
            )
            self._random_relocate(any_floor=True)
            events.extend(self._enter_room())
        elif room.feature == Feature.STAIRS_UP:
            events.append(Event("INFO", "There are stairs up here."))
        elif room.feature == Feature.STAIRS_DOWN:
            events.append(Event("INFO", "There are stairs down here."))
        elif room.feature == Feature.EXIT:
            events.append(
                Event("INFO", "You see the exit to the Dungeon of Doom here.")
            )
        else:
            events.append(Event("INFO", "This room is empty."))

        return events

    def _attempt_exit(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.EXIT:
            return [Event("INFO", "There is no exit here.")]
        if len(self.player.treasures_found) < 10:
            self.mode = Mode.GAME_OVER
            remaining = 10 - len(self.player.treasures_found)
            return [
                Event(
                    "INFO",
                    f"You abandon your quest with {remaining} treasures remaining.",
                )
            ]
        self.mode = Mode.VICTORY
        return [Event("INFO", "ALL HAIL THE VICTOR!")]

    def _use_flare(self) -> list[Event]:
        if self.player.flares < 1:
            return [Event("INFO", "Thou hast no flares.")]
        self.player.flares -= 1
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny = self.player.y + dy
                nx = self.player.x + dx
                if 0 <= ny <= 6 and 0 <= nx <= 6:
                    self.dungeon.rooms[self.player.z][ny][nx].seen = True
        return [Event("INFO", "The flare illuminates nearby rooms.")]

    def _map_grid(self) -> list[str]:
        grid: list[str] = []
        for y in range(7):
            row = []
            for x in range(7):
                room = self.dungeon.rooms[self.player.z][y][x]
                if self.player.y == y and self.player.x == x:
                    row.append("*")
                elif not room.seen:
                    row.append("?")
                else:
                    if room.monster_level > 0:
                        row.append("M")
                    elif room.treasure_id:
                        row.append("T")
                    else:
                        row.append(FEATURE_SYMBOLS.get(room.feature, "0"))
            grid.append(" ".join(row))
        return grid

    def _status_data(self) -> dict[str, int | str]:
        return {
            "gold": self.player.gold,
            "treasures": len(self.player.treasures_found),
            "flares": self.player.flares,
            "protection": self.player.spells.get(Spell.PROTECTION, 0),
            "fireball": self.player.spells.get(Spell.FIREBALL, 0),
            "lightning": self.player.spells.get(Spell.LIGHTNING, 0),
            "weaken": self.player.spells.get(Spell.WEAKEN, 0),
            "teleport": self.player.spells.get(Spell.TELEPORT, 0),
            "armor": self.player.armor_name,
            "weapon": self.player.weapon_name,
            "str": self.player.str_,
            "dex": self.player.dex,
            "iq": self.player.iq,
            "hp": self.player.hp,
            "mhp": self.player.mhp,
        }

    def _help_text(self) -> str:
        return (
            "COMMAND SUMMARY:\n"
            "L=Look at a mirror  O=Open a chest  F=use a Flare  P=Drink a potion\n"
            "R=Read a scroll     T=Status report  H=Help         M=Map\n"
            "X=eXit              U=Up             D=Down         N=North\n"
            "S=South             E=East           W=West         B=Buy\n"
            "Encounter: F=Fight  R=Run  S=Spell"
        )

    def _use_mirror(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.MIRROR:
            return [Event("INFO", "There is no mirror here.")]
        if self.rng.randint(1, 50) > self.player.iq:
            visions = [
                "The mirror is cloudy and yields no vision.",
                "You see yourself dead and lying in a black coffin.",
                "You see a dragon beckoning to you.",
                "You see the three heads of a chimaera grinning at you.",
                "You see the exit on the 7th floor, big and friendly-looking.",
            ]
            if self.rng.randint(1, 10) <= 5:
                return [Event("INFO", self.rng.choice(visions))]
            treasure = self.rng.randint(1, 10)
            tx = self.rng.randint(1, 7)
            ty = self.rng.randint(1, 7)
            return [
                Event(
                    "INFO", f"You see the {self._treasure_name(treasure)} at {tx},{ty}!"
                )
            ]

        treasure = self.rng.randint(1, 10)
        tx = self.rng.randint(1, 7)
        ty = self.rng.randint(1, 7)
        return [
            Event("INFO", f"You see the {self._treasure_name(treasure)} at {tx},{ty}!")
        ]

    def _open_chest(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.CHEST:
            return [Event("INFO", "There is no chest here.")]
        room.feature = Feature.EMPTY
        roll = self.rng.randint(1, 5)
        if roll == 1:
            self.player.armor_tier = max(0, self.player.armor_tier - 1)
            self.player.armor_name = ARMOR_NAMES[self.player.armor_tier]
            return [Event("INFO", "The perverse thing explodes, damaging your armor!")]
        if roll == 2:
            return [Event("INFO", "It containeth naught.")]
        gold = 10 + self.rng.randint(0, 20)
        self.player.gold += gold
        return [Event("INFO", f"You find {gold} gold pieces!")]

    def _read_scroll(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.SCROLL:
            return [Event("INFO", "Sorry. There is nothing to read here.")]
        room.feature = Feature.EMPTY
        spell = Spell(self.rng.randint(1, 5))
        self.player.spells[spell] = self.player.spells.get(spell, 0) + 1
        return [Event("INFO", f"The scroll contains the {spell.name.lower()} spell.")]

    def _drink_potion(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.POTION:
            return [Event("INFO", "There is no potion here, I fear.")]
        room.feature = Feature.EMPTY
        roll = self.rng.randint(1, 5)
        if roll == 1:
            heal = 5 + self.rng.randint(1, 10)
            self.player.hp = min(self.player.mhp, self.player.hp + heal)
            return [Event("INFO", "You drink the potion... healing results.")]

        change = self.rng.randint(1, 6)
        effect = self.rng.choice(
            [
                "STR",
                "DEX",
                "IQ",
                "MHP",
            ]
        )
        self._apply_attribute_change(effect, change, randomize=True)
        return [
            Event("INFO", "You drink the potion... strange energies surge through you.")
        ]

    def _open_vendor(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.VENDOR:
            return [Event("INFO", "There is no vendor here.")]
        self._shop_state = _ShopState(phase="category")
        return [
            Event(
                "PROMPT",
                "He is selling: 1> Weapons  2> Armour  3> Scrolls  4> Potions",
            )
        ]

    def _handle_shop(self, raw: str) -> list[Event]:
        if self._shop_state is None:
            return []
        state = self._shop_state
        events: list[Event] = []

        if state.phase == "category":
            if raw not in {"1", "2", "3", "4"}:
                return [Event("ERROR", "Choose 1..4.")]
            state.category = raw
            state.phase = "item"
            if raw == "1":
                events.append(
                    Event("PROMPT", "Weapons: 1> Dagger  2> Short sword  3> Broadsword")
                )
            elif raw == "2":
                events.append(
                    Event("PROMPT", "Armour: 1> Leather  2> Wooden  3> Chain mail")
                )
            elif raw == "3":
                events.append(
                    Event(
                        "PROMPT",
                        "Scrolls: 1> Protection  2> Fireball  3> Lightning  4> Weaken  5> Teleport",
                    )
                )
            else:
                events.append(
                    Event("PROMPT", "Potions: 1> Healing  2> Attribute enhancer")
                )
            return events

        if state.phase == "item":
            if state.category == "1":
                if raw not in {"1", "2", "3"}:
                    return [Event("ERROR", "Choose 1..3.")]
                tier = int(raw)
                price = WEAPON_PRICES[tier]
                if self.player.gold < price:
                    return [Event("INFO", "Don't try to cheat me. It won't work!")]
                if tier > self.player.weapon_tier:
                    self.player.weapon_tier = tier
                    self.player.weapon_name = WEAPON_NAMES[tier]
                self.player.gold -= price
                self._shop_state = None
                return [Event("INFO", "A fine weapon for your quest.")]

            if state.category == "2":
                if raw not in {"1", "2", "3"}:
                    return [Event("ERROR", "Choose 1..3.")]
                tier = int(raw)
                price = ARMOR_PRICES[tier]
                if self.player.gold < price:
                    return [Event("INFO", "Don't try to cheat me. It won't work!")]
                if tier > self.player.armor_tier:
                    self.player.armor_tier = tier
                    self.player.armor_name = ARMOR_NAMES[tier]
                self.player.gold -= price
                self._shop_state = None
                return [Event("INFO", "Armor fitted and ready.")]

            if state.category == "3":
                if raw not in {"1", "2", "3", "4", "5"}:
                    return [Event("ERROR", "Choose 1..5.")]
                spell = Spell(int(raw))
                price = SPELL_PRICES[spell]
                if self.player.gold < price:
                    return [Event("INFO", "Don't try to cheat me. It won't work!")]
                self.player.gold -= price
                self.player.spells[spell] = self.player.spells.get(spell, 0) + 1
                self._shop_state = None
                return [Event("INFO", "A scroll is yours.")]

            if state.category == "4":
                if raw not in {"1", "2"}:
                    return [Event("ERROR", "Choose 1 or 2.")]
                if raw == "1":
                    price = POTION_PRICES["HEALING"]
                    if self.player.gold < price:
                        return [Event("INFO", "Don't try to cheat me. It won't work!")]
                    self.player.gold -= price
                    self.player.hp = min(self.player.mhp, self.player.hp + 10)
                    self._shop_state = None
                    return [Event("INFO", "You quaff a healing potion.")]

                price = POTION_PRICES["ATTRIBUTE"]
                if self.player.gold < price:
                    return [Event("INFO", "Don't try to cheat me. It won't work!")]
                state.phase = "attribute"
                return [
                    Event(
                        "PROMPT",
                        "Attribute enhancer: 1> Strength  2> Dexterity  3> Intelligence  4> Max HP",
                    )
                ]

        if state.phase == "attribute":
            if raw not in {"1", "2", "3", "4"}:
                return [Event("ERROR", "Choose 1..4.")]
            price = POTION_PRICES["ATTRIBUTE"]
            if self.player.gold < price:
                self._shop_state = None
                return [Event("INFO", "Don't try to cheat me. It won't work!")]
            self.player.gold -= price
            change = self.rng.randint(1, 6)
            targets = {"1": "STR", "2": "DEX", "3": "IQ", "4": "MHP"}
            self._apply_attribute_change(targets[raw], change, randomize=False)
            self._shop_state = None
            return [Event("INFO", "The potion takes effect.")]

        return events

    def _apply_attribute_change(
        self, target: str, change: int, *, randomize: bool
    ) -> None:
        sign = self.rng.choice([-1, 1]) if randomize else 1
        delta = change * sign
        if target == "STR":
            self.player.str_ = max(1, min(18, self.player.str_ + delta))
        elif target == "DEX":
            self.player.dex = max(1, min(18, self.player.dex + delta))
        elif target == "IQ":
            self.player.iq = max(1, min(18, self.player.iq + delta))
        else:
            self.player.mhp = max(1, self.player.mhp + delta)
            self.player.hp = max(1, min(self.player.hp + delta, self.player.mhp))

    def _start_encounter(self, level: int) -> None:
        name = MONSTER_NAMES[level - 1]
        vitality = 3 * level + self.rng.randint(0, 3)
        self.encounter = Encounter(
            monster_level=level, monster_name=name, vitality=vitality
        )
        self.player.fatigued = False
        self.player.temp_armor_bonus = 0

    def _fight_round(self) -> list[Event]:
        assert self.encounter is not None
        events: list[Event] = []
        level = self.encounter.monster_level
        attack_score = (
            20 + 5 * (11 - level) + self.player.dex + 3 * self.player.weapon_tier
        )
        roll = self.rng.randint(1, 100)
        if roll > attack_score:
            events.append(
                Event("COMBAT", f"The {self.encounter.monster_name} evades your blow!")
            )
        else:
            damage = max(
                self.player.weapon_tier
                + self.player.str_ // 3
                + self.rng.randint(0, 4)
                - 2,
                1,
            )
            self.encounter.vitality -= damage
            events.append(
                Event("COMBAT", f"You hit the {self.encounter.monster_name}!")
            )
            if self.encounter.vitality <= 0:
                events.extend(self._handle_monster_death())
                return events
            if self.rng.random() < 0.05 and self.player.weapon_tier > 0:
                self.player.weapon_tier = 0
                self.player.weapon_name = "~~broken"
                events.append(Event("INFO", "Your weapon breaks with the impact!"))

        events.extend(self._monster_attack())
        return events

    def _run_attempt(self) -> list[Event]:
        assert self.encounter is not None
        if self.player.fatigued:
            return [
                Event("INFO", "You are quite fatigued after your previous efforts.")
            ]
        if self.rng.random() < 0.4:
            events = [Event("INFO", "You slip away and the monster no longer follows.")]
            self.encounter = None
            self.mode = Mode.EXPLORE
            self._random_relocate(any_floor=False)
            events.extend(self._enter_room())
            return events

        self.player.fatigued = True
        return [
            Event(
                "INFO",
                "Although you run your hardest, your efforts to escape are made in vain.",
            )
        ]

    def _monster_attack(self) -> list[Event]:
        assert self.encounter is not None
        events: list[Event] = []
        level = self.encounter.monster_level
        dodge_score = 20 + 5 * (11 - level) + 2 * self.player.dex
        roll = self.rng.randint(1, 100)
        if roll <= dodge_score:
            events.append(Event("COMBAT", "You deftly dodge the blow!"))
            return events

        armor = self.player.armor_tier + self.player.temp_armor_bonus
        damage = max(self.rng.randint(0, level - 1) + 3 - armor, 0)
        self.player.hp -= damage
        events.append(Event("COMBAT", f"The {self.encounter.monster_name} hits you!"))
        if self.player.hp <= 0:
            self.mode = Mode.GAME_OVER
            events.append(Event("INFO", "YOU HAVE DIED."))
        return events

    def _handle_monster_death(self) -> list[Event]:
        assert self.encounter is not None
        events = [Event("COMBAT", f"The foul {self.encounter.monster_name} expires.")]
        if self.rng.random() > 0.7:
            events.append(
                Event("COMBAT", "As it dies, it launches one final desperate attack.")
            )
            events.extend(self._monster_attack())

        room = self._current_room()
        if room.treasure_id:
            events.extend(self._award_treasure(room.treasure_id))
            room.treasure_id = 0
        else:
            gold = 5 * self.encounter.monster_level + self.rng.randint(0, 20)
            self.player.gold += gold
            events.append(Event("LOOT", f"You found {gold} gold pieces."))

        room.monster_level = 0
        self.encounter = None
        self.mode = Mode.EXPLORE
        return events

    def _handle_spell_choice(self, raw: str) -> list[Event]:
        self._awaiting_spell = False
        if raw not in {"1", "2", "3", "4", "5"}:
            return [Event("ERROR", "Choose 1..5.")]
        spell = Spell(int(raw))
        charges = self.player.spells.get(spell, 0)
        if self.player.iq < 12:
            return [Event("INFO", "You have insufficient intelligence.")]
        if charges <= 0:
            return [Event("INFO", "You know not that spell.")]

        self.player.spells[spell] = charges - 1
        return self._cast_spell(spell)

    def _spell_menu(self) -> dict[str, int]:
        return {
            "protection": self.player.spells.get(Spell.PROTECTION, 0),
            "fireball": self.player.spells.get(Spell.FIREBALL, 0),
            "lightning": self.player.spells.get(Spell.LIGHTNING, 0),
            "weaken": self.player.spells.get(Spell.WEAKEN, 0),
            "teleport": self.player.spells.get(Spell.TELEPORT, 0),
        }

    def _cast_spell(self, spell: Spell) -> list[Event]:
        assert self.encounter is not None
        events: list[Event] = []
        if spell == Spell.PROTECTION:
            self.player.temp_armor_bonus += 3
            events.append(
                Event("INFO", "Your armor glows briefly in response to your spell.")
            )
            events.extend(self._monster_attack())
            return events
        if spell == Spell.FIREBALL:
            damage = max(self.rng.randint(1, 5) - (self.player.iq // 3), 0)
            self.encounter.vitality -= damage
            events.append(
                Event(
                    "COMBAT",
                    f"A ball of fire scorches the {self.encounter.monster_name}.",
                )
            )
        elif spell == Spell.LIGHTNING:
            damage = max(self.rng.randint(1, 10) - (self.player.iq // 2), 0)
            self.encounter.vitality -= damage
            events.append(
                Event("COMBAT", f"The {self.encounter.monster_name} is thunderstruck!")
            )
        elif spell == Spell.WEAKEN:
            self.encounter.vitality = self.encounter.vitality // 2
            events.append(Event("COMBAT", "A green mist envelops your foe."))
        elif spell == Spell.TELEPORT:
            events.append(
                Event(
                    "INFO",
                    "Thy surroundings vibrate as you are transported elsewhere...",
                )
            )
            self.encounter = None
            self.mode = Mode.EXPLORE
            self._random_relocate(any_floor=False)
            events.extend(self._enter_room())
            return events

        if self.encounter.vitality <= 0:
            events.extend(self._handle_monster_death())
            return events

        events.extend(self._monster_attack())
        return events

    def _random_relocate(self, *, any_floor: bool) -> None:
        if any_floor:
            self.player.z = self.rng.randint(0, 6)
        while True:
            ny = self.rng.randint(0, 6)
            nx = self.rng.randint(0, 6)
            if ny == self.player.y and nx == self.player.x:
                continue
            self.player.y = ny
            self.player.x = nx
            return

    def _award_treasure(self, treasure_id: int) -> list[Event]:
        if treasure_id in self.player.treasures_found:
            return []
        self.player.treasures_found.add(treasure_id)
        return [Event("LOOT", f"You find the {self._treasure_name(treasure_id)}!")]

    def _treasure_name(self, treasure_id: int) -> str:
        return TREASURE_NAMES[treasure_id - 1]
