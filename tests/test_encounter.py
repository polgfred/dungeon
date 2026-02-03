import random

from dungeon.constants import Feature, Mode, Race
from dungeon.engine import Game
from dungeon.model import Player


def _make_game(seed: int) -> Game:
    rng = random.Random(seed)
    player = Player.create(
        rng=rng,
        race=Race.HUMAN,
        allocations={"STR": 2, "DEX": 2, "IQ": 1},
        weapon_tier=1,
        armor_tier=1,
        flare_count=0,
    )
    return Game(seed=seed, player=player, rng=rng)


def test_run_success_relocates():
    game = _make_game(1)
    game.rng = random.Random(1)
    room = game._current_room()
    room.monster_level = 1
    game._enter_room()
    start = (game.player.z, game.player.y, game.player.x)
    target = (0, 0, 0)
    target_room = game.dungeon.rooms[target[0]][target[1]][target[2]]
    target_room.monster_level = 0
    target_room.treasure_id = 0
    target_room.feature = Feature.EMPTY

    def _relocate(*_, **__) -> None:
        game.player.z, game.player.y, game.player.x = target

    game.rng.random = lambda: 0.0
    game._random_relocate = _relocate
    result = game.step("R")
    events = result.events
    assert game.mode == Mode.EXPLORE
    assert (game.player.z, game.player.y, game.player.x) != start
    assert any("turn and flee" in e.text.lower() for e in events)


def test_run_fail_sets_fatigued():
    game = _make_game(2)
    game.rng = random.Random(2)
    room = game._current_room()
    room.monster_level = 1
    game._enter_room()
    game.rng.random = lambda: 0.5
    result = game.step("R")
    events = result.events
    assert game.player.fatigued is True
    assert any("escape" in e.text for e in events)


def test_spell_prompt_uses_letter_commands():
    game = _make_game(3)
    room = game._current_room()
    room.monster_level = 1
    game._enter_room()

    result = game.step("S")
    prompt = next((e for e in result.events if e.kind == "PROMPT"), None)
    assert prompt is not None
    assert prompt.data["hasCancel"] is True
    keys = [opt["key"] for opt in prompt.data["options"]]
    assert keys == ["P", "F", "L", "W", "T"]
