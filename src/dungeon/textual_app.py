from __future__ import annotations

import argparse
import pickle
import random
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from dungeon.constants import Mode, Race
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
        margin-top: 1;
        border: round #2f5f96;
        background: #0c2443;
        color: #e8f2ff;
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

    BINDINGS = [("ctrl+c", "quit", "Quit")]

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
                yield Input(placeholder="Type a command (N/S/E/W/etc.)", id="command-input")
            with Vertical(id="right-pane"):
                yield Static("", id="stats")
                yield Static("", id="inventory")
                yield Static("", id="meta")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Dungeon of Doom (Textual Spike)"
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
        self._focus_input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.value = ""
        if not command:
            return
        game = self.game
        if game is None:
            return
        if command.startswith("/"):
            loaded_game, events = self._handle_slash_command(command, game)
            if loaded_game is not None:
                self.game = loaded_game
                game = loaded_game
                self._append_events(game.resume_events())
            else:
                self._append_events(events)
            self._refresh_panels()
            return
        if command in {"\x1b", "ESC", "esc"}:
            result = game.attempt_cancel()
        else:
            result = game.step(command)
        self._append_events(result.events)
        self._refresh_panels()
        if result.mode in {Mode.GAME_OVER, Mode.VICTORY}:
            self._disable_input()

    def _refresh_panels(self) -> None:
        game = self.game
        if game is None:
            return
        self.query_one("#map", Static).update(self._render_map(game._map_grid()))
        self._render_stats()
        self._render_prompt_help()
        self._update_input_placeholder()

    def _render_stats(self) -> None:
        game = self.game
        if game is None:
            return
        status_event = game.status_events()[0]
        data = status_event.data
        self.query_one("#stats", Static).update(
            "\n".join(
                [
                    "[b]Mode[/b]",
                    f"{game.mode.name.title()}",
                    "",
                    "[b]Stats[/b]",
                    f"STR {data['str']:>2}   DEX {data['dex']:>2}   IQ {data['iq']:>2}",
                    f"HP {data['hp']}/{data['mhp']}",
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
                    "[b]Spells[/b]",
                    f"P {data['protection']}  F {data['fireball']}  L {data['lightning']}",
                    f"W {data['weaken']}  T {data['teleport']}",
                ]
            )
        )
        self.query_one("#meta", Static).update(
            "\n".join(
                [
                    "[b]Location[/b]",
                    f"Floor {game.player.z + 1} · Room {game.player.y + 1},{game.player.x + 1}",
                    "",
                    "[dim]Tip: use command letters or Esc to cancel.[/dim]",
                    "[dim]/save [path], /load [path], and /quit are available.[/dim]",
                ]
            )
        )

    def _render_map(self, grid: list[str]) -> str:
        lines = ["[b]Dungeon Map[/b]"]
        lines.extend(grid)
        return "\n".join(lines)

    def _render_prompt_help(self) -> None:
        if not self._prompt_options:
            text = self._default_command_help()
            self.query_one("#prompt-help", Static).update(text)
            return
        lines = [f"[b]{self._prompt_text or 'Choose:'}[/b]"]
        for option in self._prompt_options:
            key = option.get("key", "?")
            label = option.get("label", "")
            disabled = option.get("disabled")
            suffix = " (unavailable)" if disabled else ""
            lines.append(f"{key}  {label}{suffix}")
        if self._prompt_has_cancel:
            lines.append("Esc  Cancel")
        self.query_one("#prompt-help", Static).update("\n".join(lines))

    def _update_input_placeholder(self) -> None:
        game = self.game
        if game is None:
            return
        prompt = game.prompt().strip()
        self.query_one("#command-input", Input).placeholder = (
            f"{prompt} enter command"
        )

    def _append_events(self, events: list[Event]) -> None:
        log = self.query_one("#event-log", RichLog)
        for event in events:
            match event.kind:
                case "INFO":
                    log.write(f"[#cfe3fa]• {event.text}[/]")
                case "ERROR":
                    log.write(f"[bold #ff8f8f]• {event.text}[/]")
                case "COMBAT":
                    log.write(f"[bold #ffe4a0]• {event.text}[/]")
                case "LOOT":
                    log.write(f"[bold #9cffbc]• {event.text}[/]")
                case "DEBUG":
                    if self.debug_mode and event.text:
                        log.write(f"[dim]{event.text}[/]")
                case "PROMPT":
                    self._prompt_text = event.text
                    self._prompt_options = list(event.data.get("options", []))
                    self._prompt_has_cancel = bool(event.data.get("hasCancel"))
                case "MAP":
                    pass
                case "STATUS":
                    pass
                case _:
                    if event.text:
                        log.write(event.text)
            if event.kind in {"INFO", "ERROR", "COMBAT", "LOOT"}:
                log.write("")
        if not any(e.kind == "PROMPT" for e in events):
            self._prompt_text = ""
            self._prompt_options = []
            self._prompt_has_cancel = False

    def _default_command_help(self) -> str:
        game = self.game
        if game is None:
            return "[b]Commands[/b]\nN S E W U D M F X L O R P B H"
        if game.mode == Mode.ENCOUNTER:
            return "\n".join(
                [
                    "[b]Encounter Commands[/b]",
                    "F  Fight",
                    "R  Run",
                    "S  Spell",
                    "Esc  Cancel spell choice",
                ]
            )
        return "\n".join(
            [
                "[b]Explore Commands[/b]",
                "N/S/E/W Move   U/D Stairs   M Map",
                "F Flare   X Exit   L Mirror",
                "O Open chest   R Read scroll   P Potion",
                "B Buy   H Help",
            ]
        )

    def _handle_slash_command(
        self, command: str, game: Game
    ) -> tuple[Game | None, list[Event]]:
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
            case "/quit" | "/q":
                self.exit()
                return None, []
        return None, [Event.error("Unknown command.")]

    def _load_game(self, path: Path) -> tuple[Game | None, list[Event]]:
        try:
            with path.open("rb") as handle:
                game = pickle.load(handle)
                if not isinstance(game, Game):
                    return None, [Event.error("Save file did not contain a game.")]
                if getattr(game, "save_version", None) != Game.SAVE_VERSION:
                    return None, [Event.error("Save file is incompatible with this version.")]
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

    def _focus_input(self) -> None:
        self.query_one("#command-input", Input).focus()

    def _disable_input(self) -> None:
        input_widget = self.query_one("#command-input", Input)
        input_widget.disabled = True
        input_widget.placeholder = "Game over. Press Ctrl+C to exit."


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
