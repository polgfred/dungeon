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
    assert any("slip away" in e.text for e in events)


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


def test_final_attack_death_ends_game_without_loot():
    game = _make_game(3)
    room = game.dungeon.rooms[game.player.z][game.player.y][game.player.x]
    room.monster_level = 1
    room.treasure_id = 1
    game._enter_room()

    session = game._encounter_session
    assert session is not None
    session.rng.random = lambda: 0.99

    def _fatal_attack():
        session.player.hp = 0
        return [], Mode.GAME_OVER

    session._monster_attack = _fatal_attack
    result = session._handle_monster_death([])
    events = result.events

    assert result.mode == Mode.GAME_OVER
    assert session.vitality == 0
    assert room.monster_level == 0
    assert 1 not in game.player.treasures_found
    assert not any(
        e.text and ("You found" in e.text or "You find" in e.text) for e in events
    )
