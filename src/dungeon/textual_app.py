from __future__ import annotations

import argparse
import pickle
import random
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.widgets import Footer, Header, RichLog, Static

from dungeon.constants import FEATURE_SYMBOLS, Feature, Mode, Race
from dungeon.engine import Game
from dungeon.model import Player
from dungeon.types import Event


def _create_default_game(*, seed: int, debug: bool) -> Game:
    rng = random.Random(seed)
    player = Player.create(
        rng=rng,
        race=Race.HUMAN,
        allocations={"STR": 2, "DEX": 2, "IQ": 1},
        weapon_tier=1,
        armor_tier=1,
        flare_count=0,
    )
    return Game(seed=seed, player=player, rng=rng, debug=debug)


class DungeonTextualApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
        background: #06162a;
        color: #d2e3f5;
    }
    #root {
        height: 1fr;
        padding: 1;
    }
    #left-pane {
        width: 1fr;
        margin: 0 1 0 0;
    }
    #right-pane {
        width: 42;
        min-width: 30;
    }
    #map {
        height: 12;
        border: round #2f5f96;
        background: #12365f;
        padding: 0 1;
    }
    #event-log {
        height: 1fr;
        border: round #2f5f96;
        background: #0a203d;
        color: #cfe3fa;
        padding: 0 1;
    }
    #prompt-help {
        height: auto;
        border: round #2f5f96;
        background: #1e4c81;
        padding: 0 1;
    }
    #command-input {
        display: none;
    }
    #stats, #inventory, #meta {
        border: round #2f5f96;
        background: #254f82;
        color: #d4e5f7;
        padding: 0 1;
        margin-bottom: 1;
        height: auto;
    }
    Header, Footer {
        background: #102e52;
        color: #d4e5f7;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+l", "load", "Load"),
    ]

    def __init__(
        self,
        *,
        seed: int = 0,
        debug: bool = False,
        continue_path: str | None = None,
    ) -> None:
        super().__init__()
        self.seed = seed
        self.debug_mode = debug
        self.continue_path = continue_path
        self.game: Game | None = None
        self.default_save = "game.sav"
        self._prompt_text = ""
        self._prompt_options: list[dict[str, object]] = []
        self._prompt_has_cancel = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="root"):
            with Vertical(id="left-pane"):
                yield Static("", id="map")
                yield RichLog(id="event-log", markup=True, wrap=True, highlight=False)
                yield Static("", id="prompt-help")
            with Vertical(id="right-pane"):
                yield Static("", id="stats")
                yield Static("", id="inventory")
                yield Static("", id="meta")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Dungeon of Doom"
        if self.continue_path:
            game, events = self._load_game(Path(self.continue_path))
            if game is None:
                self._append_events(events)
                self.game = _create_default_game(seed=self.seed, debug=self.debug_mode)
                self._append_events(
                    [Event.info("Failed to load save; started a new game instead.")]
                )
                self._append_events(self.game.start_events())
            else:
                self.game = game
                self._append_events(self.game.resume_events())
        else:
            self.game = _create_default_game(seed=self.seed, debug=self.debug_mode)
            self._append_events(self.game.start_events())
        self._refresh_panels()

    def on_key(self, event: Key) -> None:
        game = self.game
        if game is None:
            return
        key = event.key.lower()
        arrow_to_move = {
            "up": "N",
            "down": "S",
            "left": "W",
            "right": "E",
        }
        if key in arrow_to_move:
            result = game.step(arrow_to_move[key])
            self._append_events(result.events)
            self._refresh_panels()
            return
        if key == "escape":
            result = game.attempt_cancel()
            self._append_events(result.events)
            self._refresh_panels()
            return
        if len(key) != 1:
            return
        result = game.step(key.upper())
        self._append_events(result.events)
        self._refresh_panels()

    def _refresh_panels(self) -> None:
        game = self.game
        if game is None:
            return
        self.query_one("#map", Static).update(self._render_map(game))
        self._render_stats()
        self._render_prompt_help()

    def _render_stats(self) -> None:
        game = self.game
        if game is None:
            return
        status_event = game.status_events()[0]
        data = status_event.data
        hp_line = f"HP {data['hp']}/{data['mhp']}"
        if int(data["hp"]) < 10:
            hp_line = f"[bold #ff8f8f]{hp_line}[/]"
        self.query_one("#stats", Static).update(
            "\n".join(
                [
                    "[b]Mode[/b]",
                    f"{game.mode.name.title()}",
                    "",
                    "[b]Stats[/b]",
                    f"STR {data['str']:>2}   DEX {data['dex']:>2}   IQ {data['iq']:>2}",
                    hp_line,
                ]
            )
        )
        self.query_one("#inventory", Static).update(
            "\n".join(
                [
                    "[b]Inventory[/b]",
                    f"Gold: {data['gold']}",
                    f"Weapon: {data['weapon']}",
                    f"Armor: {data['armor']}",
                    f"Flares: {data['flares']}",
                    f"Treasures: {data['treasures']}/10",
                    "",
                    f"Spells: P {data['protection']}  F {data['fireball']}  "
                    f"L {data['lightning']}  W {data['weaken']}  T {data['teleport']}",
                ]
            )
        )
        self.query_one("#meta", Static).update(
            "\n".join(
                [
                    "[b]Location[/b]",
                    f"Floor {game.player.z + 1} · Room {game.player.y + 1},{game.player.x + 1}",
                ]
            )
        )

    def _render_map(self, game: Game) -> str:
        lines = ["[b]Dungeon Map[/b]"]
        for y in range(game.SIZE):
            cells: list[str] = []
            for x in range(game.SIZE):
                room = game.dungeon.rooms[game.player.z][y][x]
                if not room.seen:
                    symbol = "·"
                    display = "[#7e95b5]·[/]"
                elif room.monster_level > 0:
                    symbol = "M"
                    display = symbol
                elif room.treasure_id:
                    symbol = "T"
                    display = symbol
                else:
                    symbol = FEATURE_SYMBOLS.get(room.feature, "-")
                    display = symbol
                if y == game.player.y and x == game.player.x:
                    cells.append(f"[reverse]{symbol}[/reverse]")
                else:
                    cells.append(display)
            lines.append("  ".join(cells))
        return "\n".join(lines)

    def _render_prompt_help(self) -> None:
        if not self._prompt_options:
            text = self._default_command_help()
            self.query_one("#prompt-help", Static).update(text)
            return
        header = f"[b]{self._prompt_text or 'Choose:'}[/b]"
        options_inline: list[str] = []
        for option in self._prompt_options:
            key = option.get("key", "?")
            label = option.get("label", "")
            disabled = option.get("disabled")
            if disabled:
                options_inline.append(f"[dim]{key} {label}[/dim]")
            else:
                options_inline.append(f"{key} {label}")
        if self._prompt_has_cancel:
            options_inline.append("Esc Cancel")
        if options_inline:
            text = f"{header}  " + "   ".join(options_inline)
        else:
            text = header
        self.query_one("#prompt-help", Static).update(text)

    def _append_events(self, events: list[Event]) -> None:
        log = self.query_one("#event-log", RichLog)
        wrote_log_entry = False
        for event in events:
            match event.kind:
                case "INFO":
                    log.write(f"[#cfe3fa]• {event.text}[/]")
                    wrote_log_entry = True
                case "ERROR":
                    log.write(f"[bold #ff8f8f]• {event.text}[/]")
                    wrote_log_entry = True
                case "COMBAT":
                    log.write(f"[bold #ffe4a0]• {event.text}[/]")
                    wrote_log_entry = True
                case "LOOT":
                    log.write(f"[bold #9cffbc]• {event.text}[/]")
                    wrote_log_entry = True
                case "PROMPT":
                    self._prompt_text = event.text
                    self._prompt_options = list(event.data.get("options", []))
                    self._prompt_has_cancel = bool(event.data.get("hasCancel"))
        if wrote_log_entry:
            log.write("")
        if not any(e.kind == "PROMPT" for e in events):
            self._prompt_text = ""
            self._prompt_options = []
            self._prompt_has_cancel = False

    def _default_command_help(self) -> str:
        game = self.game
        if game is None:
            return "[b]Commands[/b] N S E W U D F X L O R P B H · Esc"

        def cmd(text: str, enabled: bool = True) -> str:
            return text if enabled else f"[dim]{text}[/dim]"

        if game.mode == Mode.ENCOUNTER:
            can_run = not game.player.fatigued
            return (
                "[b]Encounter[/b]  "
                f"{cmd('F Fight')}   {cmd('R Run', can_run)}   {cmd('S Spell')}   "
                "Esc Cancel"
            )
        room = game.dungeon.rooms[game.player.z][game.player.y][game.player.x]
        can_up = room.feature == Feature.STAIRS_UP
        can_down = room.feature == Feature.STAIRS_DOWN
        can_flare = game.player.flares > 0
        can_exit = room.feature == Feature.EXIT
        can_mirror = room.feature == Feature.MIRROR
        can_open = room.feature == Feature.CHEST
        can_read = room.feature == Feature.SCROLL
        can_potion = room.feature == Feature.POTION
        can_buy = room.feature == Feature.VENDOR
        return (
            "[b]Explore[/b]  "
            f"{cmd('N S E W Move')}   {cmd('U Up', can_up)}   {cmd('D Down', can_down)}   "
            f"{cmd('F Flare', can_flare)}   {cmd('X Exit', can_exit)}   "
            f"{cmd('L Mirror', can_mirror)}   {cmd('O Open', can_open)}   "
            f"{cmd('R Read', can_read)}   {cmd('P Potion', can_potion)}   "
            f"{cmd('B Buy', can_buy)}   {cmd('H Help')}   "
            "Esc Cancel"
        )

    def _load_game(self, path: Path) -> tuple[Game | None, list[Event]]:
        try:
            with path.open("rb") as handle:
                game = pickle.load(handle)
                if not isinstance(game, Game):
                    return None, [Event.error("Save file did not contain a game.")]
                if getattr(game, "save_version", None) != Game.SAVE_VERSION:
                    return None, [
                        Event.error("Save file is incompatible with this version.")
                    ]
                game.debug = self.debug_mode
                if game._encounter_session:
                    game._encounter_session.debug = self.debug_mode
                return game, []
        except FileNotFoundError:
            return None, [Event.error(f"Save file not found: {path}.")]
        except OSError as exc:
            return None, [Event.error(f"Load failed: {exc}.")]
        except Exception as exc:
            return None, [Event.error(f"Load failed: {exc.__class__.__name__}: {exc}.")]

    def action_save(self) -> None:
        game = self.game
        if game is None:
            return
        path = Path(self.default_save)
        try:
            with path.open("wb") as handle:
                pickle.dump(game, handle)
            self._append_events([Event.info(f"Game saved to {path}.")])
        except OSError as exc:
            self._append_events([Event.error(f"Save failed: {exc}.")])
        self._refresh_panels()

    def action_load(self) -> None:
        path = Path(self.default_save)
        loaded_game, events = self._load_game(path)
        if loaded_game is None:
            self._append_events(events)
            self._refresh_panels()
            return
        self.game = loaded_game
        self._append_events([Event.info(f"Game loaded from {path}.")])
        self._append_events(loaded_game.resume_events())
        self._refresh_panels()


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0, help="Seed for new game.")
    parser.add_argument(
        "--continue",
        dest="continue_path",
        nargs="?",
        const="game.sav",
        help="Load a save file and continue.",
    )
    parser.add_argument("--debug", action="store_true", help="Show debug events.")
    args = parser.parse_args()
    app = DungeonTextualApp(
        seed=args.seed,
        debug=args.debug,
        continue_path=args.continue_path,
    )
    app.run()


if __name__ == "__main__":
    run()
