from __future__ import annotations

import argparse
import pickle
import random
import sys
from pathlib import Path

from dungeon.constants import Race
from dungeon.engine import Game, create_player, roll_base_stats
from dungeon.types import Event


class Terminal:
    def __init__(self, *, default_save: str = "game.sav") -> None:
        self.default_save = default_save
        self.game: Game | None = None

    def run(self) -> None:
        args = self._parse_args()
        # Resume path for saved games.
        if args.continue_path:
            game, events = self._load_game(Path(args.continue_path))
            if game is None:
                self._render_events(events)
                print("Unable to load saved game.")
                return
            self._run_game(game, initial_events=game.resume_events())
            return

        # New game setup and start.
        game = self._setup_game()
        self._run_game(game, initial_events=game.start_events())

    def _setup_game(self) -> Game:
        print("Dungeon of Doom")
        print()
        seed = self._prompt_int("Seed", default=0)
        rng = random.Random(seed)
        print()
        race = self._prompt_race()

        rng_state = rng.getstate()
        base_str, base_dex, base_iq, base_hp = roll_base_stats(rng, race)
        print()
        print("Thy characteristics are as follows:")
        print(f" Strength     {base_str}")
        print(f" Dexterity    {base_dex}")
        print(f" Intelligence {base_iq}")
        print(f" Hit points   {base_hp}")

        # Allocation and starting equipment.
        print()
        allocations = self._prompt_allocations()
        gold = rng.randint(50, 60)
        print()
        weapon_tier = self._prompt_weapon(gold)
        gold -= self._price_weapon(weapon_tier)
        print()
        armor_tier = self._prompt_armor(gold)
        gold -= self._price_armor(armor_tier)
        print()
        flare_count = self._prompt_int(
            "Flares (1 gold each)", default=0, min_value=0, max_value=gold
        )
        gold -= flare_count

        # Replay RNG for deterministic starting state.
        rng.setstate(rng_state)
        player = create_player(
            rng=rng,
            race=race,
            allocations=allocations,
            weapon_tier=weapon_tier,
            armor_tier=armor_tier,
            flare_count=flare_count,
        )

        return Game(seed=seed, player=player, rng=rng)

    def _run_game(self, game: Game, *, initial_events: list[Event]) -> None:
        self.game = game
        last_events = initial_events
        self._render_turn(last_events)
        while True:
            try:
                command = input(game.prompt())
            except (KeyboardInterrupt, EOFError):
                self._clear_screen()
                print("Goodbye.")
                exit()
            # Slash commands bypass the engine command loop.
            if command.strip().startswith("/"):
                loaded_game, events = self._handle_slash_command(command, game)
                if loaded_game is not None:
                    game = loaded_game
                    self.game = game
                    last_events = game.resume_events()
                else:
                    last_events = events
                self._render_turn(last_events)
                continue
            result = game.step(command)
            last_events = result.events
            self._render_turn(last_events)
            if result.mode.name in {"GAME_OVER", "VICTORY"}:
                break

    def _render_turn(self, events: list[Event]) -> None:
        # Full-screen render of status + event log.
        self._clear_screen()
        if self.game is not None:
            self._render_events(self.game.status_events())
            print()
        self._render_events(events)
        print()

    def _render_events(self, events: list[Event]) -> None:
        for event in events:
            match event.kind:
                case "MAP":
                    for row in event.data.get("grid", []):
                        print(row)
                case "STATUS":
                    data = event.data
                    print("--------------------------------------")
                    print(
                        f"STR {data['str']:>2}  "
                        f"DEX {data['dex']:>2}  "
                        f"IQ {data['iq']:>2}  "
                        f"HP {data['hp']}/{data['mhp']}"
                    )
                    print(
                        f"GOLD {data['gold']:>3}  "
                        f"TREASURES {data['treasures']:<2}  "
                        f"FLARES {data['flares']:<2}"
                    )
                    print(
                        f"PROT {data['protection']:<2}  "
                        f"FIRE {data['fireball']:<2}  "
                        f"LIGHT {data['lightning']:<2}  "
                        f"WEAK {data['weaken']:<2}  "
                        f"TP {data['teleport']:<2}"
                    )
                    print(f"ARMOR {data['armor']}  " f"WEAPON {data['weapon']}")
                    print("--------------------------------------")
                case "PROMPT":
                    print(event.text)
                    if event.data:
                        print(
                            f"1> Protection {event.data['protection']}  "
                            f"2> Fireball {event.data['fireball']}  "
                            f"3> Lightning {event.data['lightning']}  "
                            f"4> Weaken {event.data['weaken']}  "
                            f"5> Teleport {event.data['teleport']}"
                        )
                case "INFO" | "ERROR" | "COMBAT" | "LOOT":
                    if event.text:
                        print(event.text)
                case _:
                    if event.text:
                        print(event.text)

    def _handle_slash_command(
        self, command: str, game: Game
    ) -> tuple[Game | None, list[Event]]:
        # File-based save/load commands.
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        path = Path(parts[1]) if len(parts) > 1 else Path(self.default_save)
        match cmd:
            case "/save":
                try:
                    with path.open("wb") as handle:
                        pickle.dump(game, handle)
                    return None, [Event.info(f"Game saved to {path}.")]
                except OSError as exc:
                    return None, [Event.error(f"Save failed: {exc}.")]
            case "/load":
                loaded_game, events = self._load_game(path)
                if loaded_game is None:
                    return None, events
                return loaded_game, [Event.info(f"Game loaded from {path}.")]
        return None, [Event.error("Unknown command.")]

    def _load_game(self, path: Path) -> tuple[Game | None, list[Event]]:
        # Load and validate the saved game payload.
        try:
            with path.open("rb") as handle:
                game = pickle.load(handle)
                if not isinstance(game, Game):
                    return None, [Event.error("Save file did not contain a game.")]
                return game, []
        except FileNotFoundError:
            return None, [Event.error(f"Save file not found: {path}.")]
        except OSError as exc:
            return None, [Event.error(f"Load failed: {exc}.")]
        return None, [Event.error("Load failed.")]

    def _clear_screen(self) -> None:
        print("\033c", end="")

    def _parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--continue",
            dest="continue_path",
            nargs="?",
            const=self.default_save,
            help=f"Load a save file and continue (defaults to {self.default_save}).",
        )
        return parser.parse_args(sys.argv[1:])

    def _prompt_race(self) -> Race:
        while True:
            print("Choose thy race:")
            print("  1> Human")
            print("  2> Dwarf")
            print("  3> Elf")
            print("  4> Halfling")
            choice = input("Which one? ").strip()
            if choice in {"1", "2", "3", "4"}:
                return Race(int(choice))
            print("I don't understand that.")

    def _prompt_allocations(self) -> dict[str, int]:
        remaining = 5
        allocations = {}
        for key in ("STR", "DEX", "IQ"):
            while True:
                print(f"You have {remaining} points.")
                value = self._prompt_int(
                    f"Points to add to {key}",
                    default=0,
                    min_value=0,
                    max_value=remaining,
                )
                allocations[key] = value
                remaining -= value
                break
        if remaining != 0:
            print("Allocations must total 5 points.")
            return self._prompt_allocations()
        return allocations

    def _prompt_weapon(self, gold: int) -> int:
        while True:
            print(f"You have {gold} gold pieces.")
            print("  1> Dagger 10")
            print("  2> Short sword 20")
            print("  3> Broadsword 30")
            choice = input("Which weapon? ").strip()
            if choice not in {"1", "2", "3"}:
                print("I don't understand that.")
                continue
            tier = int(choice)
            price = self._price_weapon(tier)
            if price > gold:
                print("Don't try to cheat me. It won't work!")
                continue
            return tier

    def _prompt_armor(self, gold: int) -> int:
        while True:
            print(f"You have {gold} gold pieces.")
            print("  1> Leather 10")
            print("  2> Wooden 20")
            print("  3> Chain mail 30")
            choice = input("Which armor? ").strip()
            if choice not in {"1", "2", "3"}:
                print("I don't understand that.")
                continue
            tier = int(choice)
            price = self._price_armor(tier)
            if price > gold:
                print("Don't try to cheat me. It won't work!")
                continue
            return tier

    def _price_weapon(self, tier: int) -> int:
        return {1: 10, 2: 20, 3: 30}[tier]

    def _price_armor(self, tier: int) -> int:
        return {1: 10, 2: 20, 3: 30}[tier]

    def _prompt_int(
        self,
        label: str,
        *,
        default: int | None = None,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> int:
        while True:
            prompt = f"{label}"
            if default is not None:
                prompt += f" [{default}]"
            prompt += ": "
            raw = input(prompt).strip()
            if not raw and default is not None:
                value = default
            else:
                try:
                    value = int(raw)
                except ValueError:
                    print("Enter a number.")
                    continue
            if min_value is not None and value < min_value:
                print(f"Minimum is {min_value}.")
                continue
            if max_value is not None and value > max_value:
                print(f"Maximum is {max_value}.")
                continue
            return value


def run() -> None:
    Terminal().run()


if __name__ == "__main__":
    run()
