from __future__ import annotations

import random
from dataclasses import dataclass

from dungeon.constants import MONSTER_NAMES, TREASURE_NAMES, Mode, Spell
from dungeon.model import Player, Room
from dungeon.types import Event


@dataclass
class EncounterResult:
    events: list[Event]
    mode: Mode
    relocate: bool = False
    relocate_any_floor: bool = False
    enter_room: bool = False


class EncounterSession:
    def __init__(
        self,
        *,
        rng: random.Random,
        player: Player,
        room: Room,
        monster_level: int,
        monster_name: str,
        vitality: int,
    ) -> None:
        self.rng = rng
        self.player = player
        self.room = room
        self.monster_level = monster_level
        self.monster_name = monster_name
        self.vitality = vitality
        self.awaiting_spell = False

    @classmethod
    def start(
        cls, *, rng: random.Random, player: Player, room: Room
    ) -> "EncounterSession":
        # Initialize encounter state from the room and reset temporary flags.
        level = room.monster_level
        name = MONSTER_NAMES[level - 1]
        vitality = 3 * level + rng.randint(0, 3)
        player.fatigued = False
        player.temp_armor_bonus = 0
        return cls(
            rng=rng,
            player=player,
            room=room,
            monster_level=level,
            monster_name=name,
            vitality=vitality,
        )

    def start_events(self) -> list[Event]:
        return [
            Event.combat(f"You are facing an angry {self.monster_name}!"),
            Event.info("Encounter mode: F=Fight  R=Run  S=Spell"),
        ]

    def prompt(self) -> str:
        if self.awaiting_spell:
            return "?> "
        return "F/R/S> "

    def step(self, raw: str) -> EncounterResult:
        # Input handling: pending spell selection vs action command.
        if self.awaiting_spell:
            return self._handle_spell_choice(raw)
        if not raw:
            return EncounterResult(
                [Event.error("I don't understand that.")], Mode.ENCOUNTER
            )
        key = raw[0]
        match key:
            case "F":
                return self._fight_round()
            case "R":
                return self._run_attempt()
            case "S":
                self.awaiting_spell = True
                return EncounterResult(
                    [Event.prompt("Choose a spell:", data=self._spell_menu())],
                    Mode.ENCOUNTER,
                )
            case _:
                return EncounterResult(
                    [Event.error("I don't understand that.")], Mode.ENCOUNTER
                )

    def _fight_round(self) -> EncounterResult:
        events: list[Event] = []
        level = self.monster_level
        attack_score = (
            20 + 5 * (11 - level) + self.player.dex + 3 * self.player.weapon_tier
        )

        # Resolve player attack.
        roll = self.rng.randint(1, 100)
        if roll > attack_score:
            events.append(Event.combat(f"The {self.monster_name} evades your blow!"))
        else:
            damage = max(
                self.player.weapon_tier
                + self.player.str_ // 3
                + self.rng.randint(0, 4)
                - 2,
                1,
            )
            self.vitality -= damage
            events.append(Event.combat(f"You hit the {self.monster_name}!"))
            if self.vitality <= 0:
                return self._handle_monster_death(events)
            if self.rng.random() < 0.05 and self.player.weapon_tier > 0:
                self.player.weapon_tier = 0
                self.player.weapon_name = "(Broken)"
                events.append(Event.info("Your weapon breaks with the impact!"))

        # Resolve monster response.
        attack_events, mode = self._monster_attack()
        events.extend(attack_events)
        return EncounterResult(events, mode)

    def _run_attempt(self) -> EncounterResult:
        # Attempt escape or apply fatigue.
        if self.player.fatigued:
            return EncounterResult(
                [Event.info("You are quite fatigued after your previous efforts.")],
                Mode.ENCOUNTER,
            )
        if self.rng.random() < 0.4:
            events = [Event.info("You slip away and the monster no longer follows.")]
            return EncounterResult(
                events,
                Mode.EXPLORE,
                relocate=True,
                relocate_any_floor=False,
                enter_room=True,
            )
        self.player.fatigued = True
        return EncounterResult(
            [
                Event.info(
                    "Although you run your hardest, your efforts to escape are made in vain."
                )
            ],
            Mode.ENCOUNTER,
        )

    def _monster_attack(self) -> tuple[list[Event], Mode]:
        # Resolve monster attack and damage.
        events: list[Event] = []
        level = self.monster_level
        dodge_score = 20 + 5 * (11 - level) + 2 * self.player.dex
        roll = self.rng.randint(1, 100)
        if roll <= dodge_score:
            events.append(Event.combat("You deftly dodge the blow!"))
            return events, Mode.ENCOUNTER

        armor = self.player.armor_tier + self.player.temp_armor_bonus
        damage = max(self.rng.randint(0, level - 1) + 3 - armor, 0)
        self.player.hp -= damage
        events.append(Event.combat(f"The {self.monster_name} hits you!"))
        if self.player.hp <= 0:
            events.append(Event.info("YOU HAVE DIED."))
            return events, Mode.GAME_OVER
        return events, Mode.ENCOUNTER

    def _handle_monster_death(self, events: list[Event]) -> EncounterResult:
        events.append(Event.combat(f"The foul {self.monster_name} expires."))
        # Resolve final attack, if any.
        if self.rng.random() > 0.7:
            events.append(
                Event.combat("As it dies, it launches one final desperate attack.")
            )
            attack_events, mode = self._monster_attack()
            events.extend(attack_events)
            if mode == Mode.GAME_OVER:
                self.room.monster_level = 0
                self.monster_level = 0
                self.monster_name = ""
                self.vitality = 0
                return EncounterResult(events, mode)

        # Resolve rewards and cleanup.
        if self.room.treasure_id:
            events.extend(self._award_treasure(self.room.treasure_id))
            self.room.treasure_id = 0
        else:
            gold = 5 * self.monster_level + self.rng.randint(0, 20)
            self.player.gold += gold
            events.append(Event.loot(f"You found {gold} gold pieces."))

        self.room.monster_level = 0
        self.monster_level = 0
        self.monster_name = ""
        self.vitality = 0
        return EncounterResult(events, Mode.EXPLORE)

    def _handle_spell_choice(self, raw: str) -> EncounterResult:
        # Validate selection and charges before casting.
        self.awaiting_spell = False
        if raw not in {"1", "2", "3", "4", "5"}:
            return EncounterResult([Event.error("Choose 1..5.")], Mode.ENCOUNTER)
        spell = Spell(int(raw))
        charges = self.player.spells.get(spell, 0)
        if self.player.iq < 12:
            return EncounterResult(
                [Event.info("You have insufficient intelligence.")], Mode.ENCOUNTER
            )
        if charges <= 0:
            return EncounterResult(
                [Event.info("You know not that spell.")], Mode.ENCOUNTER
            )

        self.player.spells[spell] = charges - 1
        return self._cast_spell(spell)

    def _spell_menu(self) -> dict:
        spells = self.player.spells
        return {
            "type": "spell",
            "options": {
                "protection": spells.get(Spell.PROTECTION, 0),
                "fireball": spells.get(Spell.FIREBALL, 0),
                "lightning": spells.get(Spell.LIGHTNING, 0),
                "weaken": spells.get(Spell.WEAKEN, 0),
                "teleport": spells.get(Spell.TELEPORT, 0),
            },
        }

    def _cast_spell(self, spell: Spell) -> EncounterResult:
        events: list[Event] = []
        # Apply spell effect and follow-up resolution.
        match spell:
            case Spell.PROTECTION:
                self.player.temp_armor_bonus += 3
                events.append(
                    Event.info("Your armor glows briefly in response to your spell.")
                )
                attack_events, mode = self._monster_attack()
                events.extend(attack_events)
                return EncounterResult(events, mode)
            case Spell.FIREBALL:
                damage = max(self.rng.randint(1, 5) - (self.player.iq // 3), 0)
                self.vitality -= damage
                events.append(
                    Event.combat(f"A ball of fire scorches the {self.monster_name}.")
                )
            case Spell.LIGHTNING:
                damage = max(self.rng.randint(1, 10) - (self.player.iq // 2), 0)
                self.vitality -= damage
                events.append(
                    Event.combat(f"The {self.monster_name} is thunderstruck!")
                )
            case Spell.WEAKEN:
                self.vitality = self.vitality // 2
                events.append(Event.combat("A green mist envelops your foe."))
            case Spell.TELEPORT:
                events.append(
                    Event.info(
                        "Thy surroundings vibrate as you are transported elsewhere..."
                    )
                )
                self.monster_level = 0
                self.monster_name = ""
                self.vitality = 0
                return EncounterResult(
                    events,
                    Mode.EXPLORE,
                    relocate=True,
                    relocate_any_floor=False,
                    enter_room=True,
                )

        if self.vitality <= 0:
            return self._handle_monster_death(events)
        attack_events, mode = self._monster_attack()
        events.extend(attack_events)
        return EncounterResult(events, mode)

    def _award_treasure(self, treasure_id: int) -> list[Event]:
        if treasure_id in self.player.treasures_found:
            return []
        self.player.treasures_found.add(treasure_id)
        return [Event.loot(f"You find the {TREASURE_NAMES[treasure_id - 1]}!")]
