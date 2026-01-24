from __future__ import annotations

import random

from dungeon.constants import (
    ARMOR_NAMES,
    ARMOR_PRICES,
    EXPLORE_COMMANDS,
    FEATURE_SYMBOLS,
    TREASURE_NAMES,
    WEAPON_NAMES,
    WEAPON_PRICES,
    Feature,
    Mode,
    Race,
    Spell,
)
from dungeon.encounter import EncounterSession
from dungeon.generation import generate_dungeon
from dungeon.model import Player
from dungeon.types import Event, StepResult
from dungeon.vendor import VendorSession


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
        armor_damaged=False,
        spells=spells,
    )


class Game:
    SIZE = 7

    def __init__(self, seed: int, player: Player, rng: random.Random | None = None):
        self.rng = rng or random.Random(seed)
        self.dungeon = generate_dungeon(self.rng)
        self.player = player
        self.mode = Mode.EXPLORE
        self._encounter_session: EncounterSession | None = None
        self._shop_session: VendorSession | None = None

    def start_events(self) -> list[Event]:
        return self._enter_room()

    def step(self, command: str) -> StepResult:
        events: list[Event] = []
        raw = command.strip().upper()
        if not raw:
            return StepResult(
                events=[Event.error("I don't understand that.")],
                mode=self.mode,
                needs_input=True,
            )

        # Terminal conditions short-circuit the loop.
        if self.mode in {Mode.GAME_OVER, Mode.VICTORY}:
            return StepResult(
                events=[],
                mode=self.mode,
                needs_input=False,
            )

        # Session delegation for vendor and encounter flows.
        if self._shop_session:
            result = self._shop_session.step(raw)
            events.extend(result.events)
            if result.done:
                self._shop_session = None
            return StepResult(
                events=events,
                mode=self.mode,
                needs_input=True,
            )

        if self._encounter_session:
            result = self._encounter_session.step(raw)
            events.extend(result.events)
            if result.mode != Mode.ENCOUNTER:
                self._encounter_session = None
            self.mode = result.mode
            # Follow-up relocation for run/teleport outcomes.
            if result.relocate:
                self._random_relocate(any_floor=result.relocate_any_floor)
                if result.enter_room:
                    events.extend(self._enter_room())
            return StepResult(
                events=events,
                mode=self.mode,
                needs_input=self.mode not in {Mode.GAME_OVER, Mode.VICTORY},
            )

        # Explore-mode command routing.
        key = raw[0]

        assert self.mode == Mode.EXPLORE
        if key not in EXPLORE_COMMANDS:
            return StepResult(
                events=[Event.error("I don't understand that.")],
                mode=self.mode,
                needs_input=True,
            )
        events.extend(self._handle_explore(key))
        return StepResult(
            events=events,
            mode=self.mode,
            needs_input=True,
        )

    def prompt(self) -> str:
        return self._next_prompt([])

    def status_events(self) -> list[Event]:
        return [Event.status(self._status_data())]

    def _next_prompt(self, events: list[Event]) -> str:
        # Session-driven prompts override generic ones.
        if self._shop_session:
            return self._shop_session.prompt()
        if self._encounter_session:
            return self._encounter_session.prompt()
        if any(event.kind == "PROMPT" for event in events):
            return "?> "
        return "--> "

    def resume_events(self) -> list[Event]:
        events: list[Event] = []
        # Encounter banner precedes the map on resume.
        if self._encounter_session:
            events.extend(self._encounter_session.start_events())
        events.append(Event.map(self._map_grid()))
        return events

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
            case "M":
                return [Event.map(self._map_grid())]
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
        if ny not in range(self.SIZE) or nx not in range(self.SIZE):
            return [Event.info("A wall interposes itself.")]
        self.player.y = ny
        self.player.x = nx
        return self._enter_room()

    def _stairs_up(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.STAIRS_UP:
            return [
                Event.info("There are no stairs leading up here, foolish adventurer.")
            ]
        self.player.z += 1
        return self._enter_room()

    def _stairs_down(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.STAIRS_DOWN:
            return [Event.info("There is no downward staircase here.")]
        self.player.z -= 1
        return self._enter_room()

    def _enter_room(self) -> list[Event]:
        events: list[Event] = []
        room = self._current_room()
        room.seen = True

        # Encounter start takes precedence over room features/treasure.
        if room.monster_level > 0:
            self._encounter_session = EncounterSession.start(
                rng=self.rng, player=self.player, room=room
            )
            events.extend(self._encounter_session.start_events())
            self.mode = Mode.ENCOUNTER
            return events

        if room.treasure_id:
            events.extend(self._award_treasure(room.treasure_id))
            room.treasure_id = 0

        match room.feature:
            case Feature.MIRROR:
                events.append(
                    Event.info("There is a magic mirror mounted on the wall here.")
                )
            case Feature.SCROLL:
                events.append(Event.info("There is a spell scroll here."))
            case Feature.CHEST:
                events.append(Event.info("There is a chest here."))
            case Feature.FLARES:
                gained = self.rng.randint(1, 5)
                self.player.flares += gained
                room.feature = Feature.EMPTY
                events.append(Event.info(f"You pick up {gained} flares."))
            case Feature.POTION:
                events.append(Event.info("There is a magic potion here."))
            case Feature.VENDOR:
                events.append(Event.info("There is a vendor here."))
            case Feature.THIEF:
                stolen = min(self.rng.randint(1, 50), self.player.gold)
                self.player.gold -= stolen
                room.feature = Feature.EMPTY
                events.append(Event.info(f"A thief steals {stolen} gold pieces."))
            case Feature.WARP:
                events.append(
                    Event.info(
                        "This room contains a warp. You are whisked elsewhere..."
                    )
                )
                self._random_relocate(any_floor=True)
                events.extend(self._enter_room())
            case Feature.STAIRS_UP:
                events.append(Event.info("There are stairs up here."))
            case Feature.STAIRS_DOWN:
                events.append(Event.info("There are stairs down here."))
            case Feature.EXIT:
                events.append(
                    Event.info("You see the exit to the Dungeon of Doom here.")
                )
            case _:
                events.append(Event.info("This room is empty."))

        return events

    def _attempt_exit(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.EXIT:
            return [Event.info("There is no exit here.")]
        if len(self.player.treasures_found) < 10:
            self.mode = Mode.GAME_OVER
            remaining = 10 - len(self.player.treasures_found)
            return [
                Event.info(
                    f"You abandon your quest with {remaining} treasures remaining."
                )
            ]
        self.mode = Mode.VICTORY
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
                if ny in range(self.SIZE) and nx in range(self.SIZE):
                    self.dungeon.rooms[self.player.z][ny][nx].seen = True
        return [
            Event.info("The flare illuminates nearby rooms."),
            Event.map(self._map_grid()),
        ]

    def _map_grid(self) -> list[str]:
        grid: list[str] = []
        for y in range(self.SIZE):
            row = []
            for x in range(self.SIZE):
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
            "Info: M=Map  H=Help  X=eXit\n"
            "\n"
            "Encounter: F=Fight  R=Run  S=Spell\n"
            "\n"
            "MAP LEGEND:\n"
            "0=Empty  m=Mirror  s=Scroll  c=Chest  f=Flares  p=Potion\n"
            "v=Vendor  t=Thief  w=Warp  U=Up  D=Down  X=eXit\n"
            "T=Treasure  M=Monster  *=You  ?=Unknown"
        )

    def _use_mirror(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.MIRROR:
            return [Event.info("There is no mirror here.")]
        if self.rng.randint(1, 50) > self.player.iq:
            visions = [
                "The mirror is cloudy and yields no vision.",
                "You see yourself dead and lying in a black coffin.",
                "You see a dragon beckoning to you.",
                "You see the three heads of a chimaera grinning at you.",
                "You see the exit on the 7th floor, big and friendly-looking.",
            ]
            if self.rng.randint(1, 10) <= 5:
                return [Event.info(self.rng.choice(visions))]
            treasure = self.rng.randint(1, 10)
            tx = self.rng.randint(1, self.SIZE)
            ty = self.rng.randint(1, self.SIZE)
            tz = self.rng.randint(1, self.SIZE)
            return [
                Event.info(
                    f"You see the {self._treasure_name(treasure)} at {tz},{ty},{tx}!"
                )
            ]

        locations = [
            (room.treasure_id, z, y, x)
            for z, floor in enumerate(self.dungeon.rooms)
            for y, row in enumerate(floor)
            for x, room in enumerate(row)
            if room.treasure_id and room.treasure_id not in self.player.treasures_found
        ]
        if not locations:
            return [Event.info("The mirror is cloudy and yields no vision.")]
        treasure, z, y, x = self.rng.choice(locations)
        return [
            Event.info(
                f"You see the {self._treasure_name(treasure)} at {z + 1},{y + 1},{x + 1}!"
            )
        ]

    def _open_chest(self) -> list[Event]:
        room = self._current_room()
        if room.feature != Feature.CHEST:
            return [Event.info("There is no chest here.")]
        room.feature = Feature.EMPTY
        roll = self.rng.randint(1, 5)
        match roll:
            case 1:
                return [Event.info("It containeth naught.")]
            case 2:
                if self.player.armor_tier > 0:
                    self.player.armor_tier -= 1
                    self.player.armor_damaged = True
                return [Event.info("The perverse thing explodes, damaging your armor!")]
            case _:
                gold = 10 + self.rng.randint(0, 20)
                self.player.gold += gold
                return [Event.info(f"You find {gold} gold pieces!")]

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
            return [Event.info("You drink the potion... healing results.")]

        effect = self.rng.choice(["STR", "DEX", "IQ", "MHP"])
        change = self.rng.randint(1, 6)
        if self.rng.random() > 0.5:
            change = -change
        self.player.apply_attribute_change(target=effect, change=change)
        return [
            Event.info("You drink the potion... strange energies surge through you.")
        ]

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
