from __future__ import annotations

import random

from dungeon.constants import (
    ARMOR_NAMES,
    EXPLORE_COMMANDS,
    FEATURE_SYMBOLS,
    MONSTER_NAMES,
    TREASURE_NAMES,
    Feature,
    Mode,
    Spell,
)
from dungeon.encounter import EncounterSession
from dungeon.generation import generate_dungeon
from dungeon.model import Player
from dungeon.potions import drink_attribute_potion_events, drink_healing_potion_events
from dungeon.types import Event, StepResult
from dungeon.vendor import VendorSession


def _pluralize(count: int, singular: str, plural: str | None = None) -> str:
    suffix = plural if plural is not None else f"{singular}s"
    return singular if count == 1 else suffix


class Game:
    SIZE = 7
    SAVE_VERSION = 1

    def __init__(
        self,
        *,
        seed: int,
        player: Player,
        rng: random.Random | None = None,
        debug: bool = False,
    ) -> None:
        self.save_version = self.SAVE_VERSION
        self.rng = rng or random.Random(seed)
        self.player = player
        self.dungeon = generate_dungeon(self.rng)
        self._end_mode: Mode | None = None
        self._encounter_session: EncounterSession | None = None
        self._shop_session: VendorSession | None = None
        self.debug = debug

    @property
    def mode(self) -> Mode:
        if self._end_mode is not None:
            return self._end_mode
        if self._encounter_session is not None:
            return Mode.ENCOUNTER
        return Mode.EXPLORE

    def start_events(self) -> list[Event]:
        return self._enter_room()

    def step(self, command: str) -> StepResult:
        raw = command.strip().upper()
        if not raw:
            return StepResult(
                events=[Event.error("I don't understand that.")],
                mode=self.mode,
                needs_input=True,
            )
        if self.mode in {Mode.GAME_OVER, Mode.VICTORY}:
            return StepResult(
                events=[Event.error("I don't understand that.")],
                mode=self.mode,
                needs_input=False,
            )

        if self._shop_session:
            result = self._shop_session.step(raw)
            if result.done:
                self._shop_session = None
            return StepResult(events=result.events, mode=self.mode, needs_input=True)

        if self._encounter_session:
            result = self._encounter_session.step(raw)
            events = result.events
            if result.done:
                self._encounter_session = None
                if result.defeated_monster:
                    room = self._current_room()
                    monster_level = room.monster_level
                    room.monster_level = 0
                    if self.player.hp > 0:
                        if room.treasure_id:
                            events.extend(self._award_treasure(room.treasure_id))
                            room.treasure_id = 0
                        else:
                            gold = 5 * monster_level + self.rng.randint(0, 20)
                            self.player.gold += gold
                            events.append(
                                Event.loot(
                                    f"You find {gold} gold {_pluralize(gold, 'piece')}."
                                )
                            )
                if result.relocate:
                    self._random_relocate(any_floor=result.relocate_any_floor)
                    if result.enter_room:
                        events.extend(self._enter_room())
                if self.player.hp <= 0:
                    self._end_mode = Mode.GAME_OVER
            return StepResult(events=events, mode=self.mode, needs_input=True)

        key = raw[0]
        if key not in EXPLORE_COMMANDS:
            return StepResult(
                events=[Event.error("I don't understand that.")],
                mode=self.mode,
                needs_input=True,
            )
        return StepResult(events=self._handle_explore(key), mode=self.mode, needs_input=True)

    def attempt_cancel(self) -> StepResult:
        if self.mode in {Mode.GAME_OVER, Mode.VICTORY}:
            return StepResult(events=[], mode=self.mode, needs_input=False)
        if self._shop_session:
            result = self._shop_session.attempt_cancel()
            if result.done:
                self._shop_session = None
            return StepResult(events=result.events, mode=self.mode, needs_input=True)
        if self._encounter_session:
            result = self._encounter_session.attempt_cancel()
            events = result.events
            if result.done:
                self._encounter_session = None
                if self.player.hp <= 0:
                    self._end_mode = Mode.GAME_OVER
            if result.relocate:
                self._random_relocate(any_floor=result.relocate_any_floor)
                if result.enter_room:
                    events.extend(self._enter_room())
            return StepResult(events=events, mode=self.mode, needs_input=True)
        return StepResult(
            events=[Event.info("I don't understand that.")],
            mode=self.mode,
            needs_input=True,
        )

    def prompt(self) -> str:
        if self._shop_session:
            return self._shop_session.prompt()
        if self._encounter_session:
            return self._encounter_session.prompt()
        return "--> "

    def status_events(self) -> list[Event]:
        events = [Event.status(self._status_data())]
        if self.debug:
            events.append(
                Event.debug(
                    "DEBUG STATS: "
                    f"weapon_tier={self.player.weapon_tier} "
                    f"armor_tier={self.player.armor_tier} "
                    f"weapon_broken={self.player.weapon_broken} "
                    f"armor_damaged={self.player.armor_damaged} "
                    f"temp_armor_bonus={self.player.temp_armor_bonus} "
                    f"fatigued={self.player.fatigued}"
                )
            )
        return events

    def resume_events(self) -> list[Event]:
        if self._shop_session:
            return [
                Event.info("There is a vendor here. Do you wish to purchase something?"),
                *self._shop_session.resume_events(),
            ]
        if self._encounter_session:
            return self._encounter_session.resume_events()
        return self._describe_room(self._current_room())

    def _current_room(self):
        return self.dungeon.rooms[self.player.z][self.player.y][self.player.x]

    def _handle_explore(self, key: str) -> list[Event]:
        match key:
            case "N":
                return self._move(-1, 0)
            case "S":
                return self._move(1, 0)
            case "E":
                return self._move(0, 1)
            case "W":
                return self._move(0, -1)
            case "U":
                return self._stairs_up()
            case "D":
                return self._stairs_down()
            case "F":
                return self._use_flare()
            case "X":
                return self._attempt_exit()
            case "L":
                return self._use_mirror()
            case "O":
                return self._open_chest()
            case "R":
                return self._read_scroll()
            case "P":
                return self._drink_potion()
            case "B":
                return self._open_vendor()
            case "H":
                return [Event.info(self._help_text())]
            case _:
                return []

    def _move(self, dy: int, dx: int) -> list[Event]:
        ny = self.player.y + dy
        nx = self.player.x + dx
        if ny < 0 or ny >= self.SIZE or nx < 0 or nx >= self.SIZE:
            return [Event.info("A wall interposes itself.")]
        self.player.y = ny
        self.player.x = nx
        return self._enter_room()

    def _stairs_up(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.STAIRS_UP:
            return [Event.info("There are no stairs leading up here, foolish adventurer.")]
        self.player.z += 1
        return self._enter_room()

    def _stairs_down(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.STAIRS_DOWN:
            return [
                Event.info(
                    "There is no downward staircase here, so how do you propose to go down?"
                )
            ]
        self.player.z -= 1
        return self._enter_room()

    def _enter_room(self) -> list[Event]:
        events: list[Event] = []
        room = self._current_room()
        room.seen = True

        if room.monster_level > 0:
            self._encounter_session = EncounterSession.start(
                rng=self.rng,
                player=self.player,
                monster_level=room.monster_level,
                debug=self.debug,
            )
            return self._encounter_session.start_events()

        if room.treasure_id:
            events.extend(self._award_treasure(room.treasure_id))
            room.treasure_id = 0

        match room.feature:
            case Feature.FLARES:
                gained = self.rng.randint(1, 5)
                self.player.flares += gained
                room.feature = Feature.EMPTY
                events.append(Event.info("You pick up some flares here."))
            case Feature.THIEF:
                stolen = min(self.rng.randint(1, 50), self.player.gold)
                self.player.gold -= stolen
                room.feature = Feature.EMPTY
                events.append(
                    Event.info(
                        f"A thief sneaks from the shadows and removes {stolen} gold "
                        f"{_pluralize(stolen, 'piece')} from your possession."
                    )
                )
            case Feature.WARP:
                events.append(
                    Event.info(
                        "This room contains a warp. Before you realize what is going on, "
                        "you appear elsewhere..."
                    )
                )
                self._random_relocate(any_floor=True)
                events.extend(self._enter_room())
            case _:
                events.extend(self._describe_room(room))
        return events

    def _describe_room(self, room) -> list[Event]:
        events: list[Event] = []
        if room.monster_level > 0:
            name = MONSTER_NAMES[room.monster_level - 1]
            return [Event.combat(f"You are facing an angry {name}!")]
        if room.treasure_id:
            events.append(Event.loot(f"You find the {self._treasure_name(room.treasure_id)}!"))
        match room.feature:
            case Feature.MIRROR:
                events.append(Event.info("There is a magic mirror mounted on the wall here."))
            case Feature.SCROLL:
                events.append(Event.info("There is a spell scroll here."))
            case Feature.CHEST:
                events.append(Event.info("There is a chest here."))
            case Feature.POTION:
                events.append(Event.info("There is a magic potion here."))
            case Feature.VENDOR:
                events.append(
                    Event.info("There is a vendor here. Do you wish to purchase something?")
                )
            case Feature.STAIRS_UP:
                events.append(Event.info("There are stairs up here."))
            case Feature.STAIRS_DOWN:
                events.append(Event.info("There are stairs down here."))
            case Feature.EXIT:
                events.append(Event.info("You see the exit to the DUNGEON of DOOM here."))
            case _:
                events.append(Event.info("This room is empty."))
        return events

    def _attempt_exit(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.EXIT:
            return [Event.info("There is no exit here.")]
        if len(self.player.treasures_found) < 10:
            self._end_mode = Mode.GAME_OVER
            remaining = 10 - len(self.player.treasures_found)
            return [
                Event.info("What? And hast thou abandoned thy quest before it was accomplished?"),
                Event.info(
                    "The DUNGEON of DOOM still holds "
                    f"{remaining} treasures that thine eyes shall never behold! "
                    "Verily thy triumph is incomplete!"
                ),
            ]
        self._end_mode = Mode.VICTORY
        return [Event.info("ALL HAIL THE VICTOR!")]

    def _use_flare(self) -> list[Event]:
        if self.player.flares < 1:
            return [Event.info("Thou hast no flares.")]
        self.player.flares -= 1
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny = self.player.y + dy
                nx = self.player.x + dx
                if ny >= 0 and ny < self.SIZE and nx >= 0 and nx < self.SIZE:
                    self.dungeon.rooms[self.player.z][ny][nx].seen = True
        return [Event.info("The flare illuminates nearby rooms.")]

    def _map_grid(self) -> list[str]:
        grid: list[str] = []
        for y in range(self.SIZE):
            row: list[str] = []
            for x in range(self.SIZE):
                room = self.dungeon.rooms[self.player.z][y][x]
                if self.player.y == y and self.player.x == x:
                    row.append("*")
                elif not room.seen:
                    row.append("·")
                elif room.monster_level > 0:
                    row.append("M")
                elif room.treasure_id:
                    row.append("T")
                else:
                    row.append(FEATURE_SYMBOLS.get(room.feature, "-"))
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
            "armor": self._armor_display_name(),
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
            "Move: N=North  S=South  E=East  W=West  U=Up  D=Down\n"
            "Act:  L=Look  O=Open chest  R=Read scroll  P=Potion  F=Flare  B=Buy\n"
            "Info: H=Help  X=eXit\n"
            "\n"
            "Encounter: F=Fight  R=Run  S=Spell\n"
            "\n"
            "MAP LEGEND:\n"
            "-=Empty  m=Mirror  s=Scroll  c=Chest  f=Flares  p=Potion\n"
            "v=Vendor  t=Thief  w=Warp  U=Up  D=Down  X=eXit\n"
            "T=Treasure  M=Monster  *=You  ·=Unknown"
        )

    def _use_mirror(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.MIRROR:
            return [Event.info("There is no mirror here.")]
        events: list[Event] = []
        if len(self.player.treasures_found) == 10:
            events.append(Event.info("The mirror is cloudy and yields no vision."))
        elif self.rng.randint(1, 50) > self.player.iq:
            visions = [
                "The mirror is cloudy and yields no vision.",
                "You see yourself dead and lying in a black coffin.",
                "You see a dragon beckoning to you.",
                "You see the three heads of a chimaera grinning at you.",
                "You see the exit on the 7th floor, big and friendly-looking.",
            ]
            if self.rng.randint(1, 10) <= 5:
                events.append(Event.info(self.rng.choice(visions)))
            else:
                treasure = self.rng.randint(1, 10)
                tx = self.rng.randint(1, self.SIZE)
                ty = self.rng.randint(1, self.SIZE)
                tz = self.rng.randint(1, self.SIZE)
                events.append(
                    Event.info(f"You see the {self._treasure_name(treasure)} at {tz},{ty},{tx}!")
                )
        else:
            locations = [
                (candidate.treasure_id, z, y, x)
                for z, floor in enumerate(self.dungeon.rooms)
                for y, row in enumerate(floor)
                for x, candidate in enumerate(row)
                if candidate.treasure_id
                and candidate.treasure_id not in self.player.treasures_found
            ]
            if not locations:
                events.append(Event.info("The mirror is cloudy and yields no vision."))
            else:
                treasure, z, y, x = self.rng.choice(locations)
                events.append(
                    Event.info(
                        f"You see the {self._treasure_name(treasure)} at {z + 1},{y + 1},{x + 1}!"
                    )
                )
        room.feature = Feature.EMPTY
        return events

    def _open_chest(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.CHEST:
            return [Event.info("There is no chest here.")]
        room.feature = Feature.EMPTY
        roll = self.rng.randint(1, 10)
        if roll == 1:
            if self.player.armor_tier > 0:
                self.player.armor_tier -= 1
                if self.player.armor_tier == 0:
                    self.player.armor_name = ARMOR_NAMES[0]
                    self.player.armor_damaged = False
                    return [
                        Event.info(
                            "The perverse thing explodes as you open it, destroying your armour!"
                        )
                    ]
                self.player.armor_damaged = True
                return [
                    Event.info(
                        "The perverse thing explodes as you open it, damaging your armour!"
                    )
                ]
            self.player.armor_name = ARMOR_NAMES[0]
            self.player.armor_damaged = False
            self.player.hp -= self.rng.randint(0, 4) + 3
            if self.player.hp <= 0:
                self._end_mode = Mode.GAME_OVER
                return [
                    Event.info("The perverse thing explodes as you open it, wounding you!"),
                    Event.info("YOU HAVE DIED."),
                ]
            return [Event.info("The perverse thing explodes as you open it, wounding you!")]
        if roll in {2, 3, 4}:
            return [Event.info("It containeth naught.")]
        gold = 10 + self.rng.randint(0, 20)
        self.player.gold += gold
        return [Event.info(f"You find {gold} gold {_pluralize(gold, 'piece')}!")]

    def _read_scroll(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.SCROLL:
            return [Event.info("Sorry. There is nothing to read here.")]
        room.feature = Feature.EMPTY
        spell = Spell(self.rng.randint(1, 5))
        self.player.spells[spell] = self.player.spells.get(spell, 0) + 1
        return [Event.info(f"The scroll contains the {spell.name.lower()} spell.")]

    def _drink_potion(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.POTION:
            return [Event.info("There is no potion here, I fear.")]
        room.feature = Feature.EMPTY
        roll = self.rng.randint(1, 5)
        if roll == 1:
            heal = 5 + self.rng.randint(1, 10)
            self.player.hp = min(self.player.mhp, self.player.hp + heal)
            return drink_healing_potion_events()
        effect = self.rng.choice(["STR", "DEX", "IQ", "MHP"])
        change = self.rng.randint(1, 3)
        if self.rng.random() > 0.5:
            change = -change
        self.player.apply_attribute_change(target=effect, change=change)
        return drink_attribute_potion_events(target=effect, change=change)

    def _open_vendor(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.VENDOR:
            return [Event.info("There is no vendor here.")]
        self._shop_session = VendorSession(rng=self.rng, player=self.player)
        return self._shop_session.start_events()

    def _armor_display_name(self) -> str:
        if self.player.armor_damaged:
            return f"{self.player.armor_name} (damaged)"
        return self.player.armor_name

    def _random_relocate(self, *, any_floor: bool) -> None:
        if any_floor:
            self.player.z = self.rng.randrange(self.SIZE)
        while True:
            ny = self.rng.randrange(self.SIZE)
            nx = self.rng.randrange(self.SIZE)
            if ny == self.player.y and nx == self.player.x:
                continue
            self.player.y = ny
            self.player.x = nx
            return

    def _award_treasure(self, treasure_id: int) -> list[Event]:
        if treasure_id in self.player.treasures_found:
            return []
        self.player.treasures_found.add(treasure_id)
        return [Event.loot(f"You find the {self._treasure_name(treasure_id)}!")]

    def _treasure_name(self, treasure_id: int) -> str:
        return TREASURE_NAMES[treasure_id - 1]
