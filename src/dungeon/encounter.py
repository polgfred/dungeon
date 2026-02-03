from __future__ import annotations

import math
import random
from dataclasses import dataclass

from dungeon.constants import MONSTER_NAMES, Spell
from dungeon.model import Player
from dungeon.types import Event


@dataclass
class EncounterResult:
    events: list[Event]
    done: bool = False
    defeated_monster: bool = False
    relocate: bool = False
    relocate_any_floor: bool = False
    enter_room: bool = False


def _reset_player_after_encounter(player: Player) -> None:
    player.fatigued = False
    player.temp_armor_bonus = 0


class EncounterSession:
    def __init__(
        self,
        *,
        rng: random.Random,
        player: Player,
        monster_level: int,
        monster_name: str,
        vitality: int,
        debug: bool,
    ) -> None:
        self.rng = rng
        self.player = player
        self.monster_level = monster_level
        self.monster_name = monster_name
        self.vitality = vitality
        self.awaiting_spell = False
        self.debug = debug

    @classmethod
    def start(
        cls,
        *,
        rng: random.Random,
        player: Player,
        monster_level: int,
        debug: bool,
    ) -> "EncounterSession":
        name = MONSTER_NAMES[monster_level - 1]
        vitality = 3 * monster_level + rng.randint(0, 3)
        _reset_player_after_encounter(player)
        return cls(
            rng=rng,
            player=player,
            monster_level=monster_level,
            monster_name=name,
            vitality=vitality,
            debug=debug,
        )

    def start_events(self) -> list[Event]:
        events = [Event.combat(f"You are facing an angry {self.monster_name}!")]
        if self.debug:
            events.append(self._debug_monster_event())
        return events

    def resume_events(self) -> list[Event]:
        if self.awaiting_spell:
            return [Event.prompt("Choose a spell:", options=self._spell_menu())]
        return self.start_events()

    def prompt(self) -> str:
        return "?> " if self.awaiting_spell else "F/R/S> "

    def attempt_cancel(self) -> EncounterResult:
        if not self.awaiting_spell:
            return self._with_debug(
                EncounterResult(events=[Event.info("I don't understand that.")])
            )
        self.awaiting_spell = False
        return self._with_debug(
            EncounterResult(events=[Event.info("You ready yourself for the fight.")])
        )

    def step(self, raw: str) -> EncounterResult:
        if self.awaiting_spell:
            return self._with_debug(self._handle_spell_choice(raw))
        if not raw:
            return self._with_debug(
                EncounterResult(events=[Event.error("I don't understand that.")])
            )
        key = raw[0]
        match key:
            case "F":
                return self._with_debug(self._fight_round())
            case "R":
                return self._with_debug(self._run_attempt())
            case "S":
                self.awaiting_spell = True
                return self._with_debug(
                    EncounterResult(
                        events=[Event.prompt("Choose a spell:", options=self._spell_menu())]
                    )
                )
            case _:
                return self._with_debug(
                    EncounterResult(events=[Event.error("I don't understand that.")])
                )

    def _with_debug(self, result: EncounterResult) -> EncounterResult:
        if not self.debug:
            return result
        result.events.append(self._debug_monster_event())
        return result

    def _debug_monster_event(self) -> Event:
        return Event.debug(
            f"DEBUG MONSTER: name={self.monster_name} level={self.monster_level} vitality={self.vitality}"
        )

    def _fight_round(self) -> EncounterResult:
        events: list[Event] = []
        level = self.monster_level
        attack_score = (
            20 + 5 * (11 - level) + self.player.dex + 3 * self.player.weapon_tier
        )
        roll = self.rng.randint(1, 100)
        if self.debug:
            events.append(
                Event.debug(
                    "DEBUG FIGHT: "
                    f"attack_score={attack_score} roll={roll} "
                    f"weapon_tier={self.player.weapon_tier} str={self.player.str_} dex={self.player.dex}"
                )
            )
        if roll > attack_score:
            events.append(Event.combat(f"The {self.monster_name} evades your blow!"))
        else:
            damage = max(
                self.player.weapon_tier
                + math.floor(self.player.str_ / 3)
                + self.rng.randint(0, 4)
                - 2,
                1,
            )
            self.vitality -= damage
            events.append(Event.combat(f"You hit the {self.monster_name}!"))
            if self.debug:
                events.append(
                    Event.debug(f"DEBUG FIGHT: damage={damage} vitality={self.vitality}")
                )
            if self.vitality <= 0:
                return self._handle_monster_death(events)
            if self.rng.random() < 0.05 and self.player.weapon_tier > 0:
                self.player.weapon_tier = 0
                self.player.weapon_broken = True
                events.append(Event.info("Your weapon breaks with the impact!"))

        attack_result = self._monster_attack()
        events.extend(attack_result.events)
        return EncounterResult(events=events, done=attack_result.done)

    def _run_attempt(self) -> EncounterResult:
        if self.player.fatigued:
            return EncounterResult(
                events=[Event.info("You are quite fatigued after your previous efforts.")]
            )
        if self.rng.random() < 0.4:
            _reset_player_after_encounter(self.player)
            return EncounterResult(
                events=[
                    Event.info(
                        f"You turn and flee, the vile {self.monster_name} following close behind."
                    ),
                    Event.info(
                        f"Suddenly, you realize that the {self.monster_name} is no longer following you."
                    ),
                ],
                done=True,
                relocate=True,
                relocate_any_floor=False,
                enter_room=True,
            )
        self.player.fatigued = True
        return EncounterResult(
            events=[
                Event.info(
                    "Although you run your hardest, your efforts to escape are made in vain."
                )
            ]
        )

    def _monster_attack(self) -> EncounterResult:
        events: list[Event] = []
        level = self.monster_level
        dodge_score = 20 + 5 * (11 - level) + 2 * self.player.dex
        roll = self.rng.randint(1, 100)
        if self.debug:
            events.append(
                Event.debug(
                    "DEBUG MONSTER: "
                    f"dodge_score={dodge_score} roll={roll} "
                    f"armor_tier={self.player.armor_tier} temp_armor_bonus={self.player.temp_armor_bonus}"
                )
            )
        if roll <= dodge_score:
            events.append(Event.combat("You deftly dodge the blow!"))
            return EncounterResult(events=events)

        armor = self.player.armor_tier + self.player.temp_armor_bonus
        damage = max(
            self.rng.randint(0, level - 1) + math.floor(2.5 + level / 3) - armor,
            0,
        )
        self.player.hp -= damage
        events.append(Event.combat(f"The {self.monster_name} hits you!"))
        if self.debug:
            events.append(Event.debug(f"DEBUG MONSTER: damage={damage} hp={self.player.hp}"))
        if self.player.hp <= 0:
            events.append(Event.info("YOU HAVE DIED."))
            return EncounterResult(events=events, done=True)
        return EncounterResult(events=events)

    def _handle_monster_death(self, events: list[Event]) -> EncounterResult:
        events.append(Event.combat(f"The foul {self.monster_name} expires."))
        if self.rng.random() > 0.7:
            events.append(
                Event.combat("As he dies, though, he launches one final desperate attack.")
            )
            attack_result = self._monster_attack()
            events.extend(attack_result.events)
            if attack_result.done:
                self.monster_level = 0
                self.monster_name = ""
                self.vitality = 0
                return EncounterResult(events=events, done=True, defeated_monster=True)

        self.monster_level = 0
        self.monster_name = ""
        self.vitality = 0
        _reset_player_after_encounter(self.player)
        return EncounterResult(events=events, done=True, defeated_monster=True)

    def _handle_spell_choice(self, raw: str) -> EncounterResult:
        self.awaiting_spell = False
        spell_map = {
            "P": Spell.PROTECTION,
            "F": Spell.FIREBALL,
            "L": Spell.LIGHTNING,
            "W": Spell.WEAKEN,
            "T": Spell.TELEPORT,
        }
        spell = spell_map.get(raw[:1])
        if spell is None:
            return EncounterResult(events=[Event.error("Choose P/F/L/W/T or Esc to cancel.")])
        charges = self.player.spells.get(spell, 0)
        if self.player.iq < 12:
            return EncounterResult(events=[Event.info("You have insufficient intelligence.")])
        if charges <= 0:
            return EncounterResult(events=[Event.info("You know not that spell.")])

        self.player.spells[spell] = charges - 1
        return self._cast_spell(spell)

    def _spell_menu(self) -> list[dict[str, object]]:
        iq_too_low = self.player.iq < 12
        spells = self.player.spells
        return [
            {
                "key": "P",
                "label": f"Protection ({spells.get(Spell.PROTECTION, 0)})",
                "disabled": iq_too_low or spells.get(Spell.PROTECTION, 0) <= 0,
            },
            {
                "key": "F",
                "label": f"Fireball ({spells.get(Spell.FIREBALL, 0)})",
                "disabled": iq_too_low or spells.get(Spell.FIREBALL, 0) <= 0,
            },
            {
                "key": "L",
                "label": f"Lightning ({spells.get(Spell.LIGHTNING, 0)})",
                "disabled": iq_too_low or spells.get(Spell.LIGHTNING, 0) <= 0,
            },
            {
                "key": "W",
                "label": f"Weaken ({spells.get(Spell.WEAKEN, 0)})",
                "disabled": iq_too_low or spells.get(Spell.WEAKEN, 0) <= 0,
            },
            {
                "key": "T",
                "label": f"Teleport ({spells.get(Spell.TELEPORT, 0)})",
                "disabled": iq_too_low or spells.get(Spell.TELEPORT, 0) <= 0,
            },
        ]

    def _cast_spell(self, spell: Spell) -> EncounterResult:
        events: list[Event] = []
        match spell:
            case Spell.PROTECTION:
                self.player.temp_armor_bonus += 3
                if self.player.armor_tier > 0:
                    events.append(
                        Event.info("Your armour glows briefly in response to your spell.")
                    )
                else:
                    events.append(
                        Event.info(
                            "Your clothes glow briefly, becoming, temporarily, armour."
                        )
                    )
            case Spell.FIREBALL:
                roll = self.rng.randint(1, 5)
                damage = roll + math.floor(self.player.iq / 3)
                self.vitality -= damage
                events.append(
                    Event.combat(
                        f"A glowing ball of fire converges with the {self.monster_name}."
                    )
                )
            case Spell.LIGHTNING:
                roll = self.rng.randint(1, 10)
                damage = roll + math.floor(self.player.iq / 2)
                self.vitality -= damage
                events.append(Event.combat(f"The {self.monster_name} is thunderstruck!"))
            case Spell.WEAKEN:
                self.vitality = math.floor(self.vitality / 2)
                events.append(
                    Event.combat(
                        f"A green mist envelops the {self.monster_name}, depriving him of half his vitality."
                    )
                )
            case Spell.TELEPORT:
                events.append(
                    Event.info(
                        "Thy surroundings vibrate momentarily, as you are magically transported elsewhere..."
                    )
                )
                self.monster_level = 0
                self.monster_name = ""
                self.vitality = 0
                _reset_player_after_encounter(self.player)
                return EncounterResult(
                    events=events,
                    done=True,
                    relocate=True,
                    relocate_any_floor=False,
                    enter_room=True,
                )

        if self.vitality <= 0:
            return self._handle_monster_death(events)
        attack_result = self._monster_attack()
        events.extend(attack_result.events)
        return EncounterResult(events=events, done=attack_result.done)
