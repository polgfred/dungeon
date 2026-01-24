import random

from dungeon.constants import Feature, Race
from dungeon.engine import Game, create_player
from dungeon.model import Encounter
from dungeon.constants import Mode


def _make_game(seed: int) -> Game:
    rng = random.Random(seed)
    player = create_player(
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
    game.encounter = Encounter(monster_level=1, monster_name="Skeleton", vitality=5)
    game.mode = Mode.ENCOUNTER
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
    events = game._run_attempt()
    assert game.mode == game.mode.EXPLORE
    assert (game.player.z, game.player.y, game.player.x) != start
    assert any("slip away" in e.text for e in events)


def test_run_fail_sets_fatigued():
    game = _make_game(2)
    game.rng = random.Random(2)
    game.encounter = Encounter(monster_level=1, monster_name="Skeleton", vitality=5)
    game.mode = Mode.ENCOUNTER
    events = game._run_attempt()
    assert game.player.fatigued is True
    assert any("escape" in e.text for e in events)


def test_final_attack_death_ends_game_without_loot():
    game = _make_game(3)
    game.encounter = Encounter(monster_level=1, monster_name="Skeleton", vitality=1)
    game.mode = Mode.ENCOUNTER
    room = game.dungeon.rooms[game.player.z][game.player.y][game.player.x]
    room.monster_level = 1
    room.treasure_id = 1

    game.rng.random = lambda: 0.99

    def _fatal_attack() -> list:
        game.player.hp = 0
        game.mode = Mode.GAME_OVER
        return []

    game._monster_attack = _fatal_attack
    events = game._handle_monster_death()

    assert game.mode == Mode.GAME_OVER
    assert game.encounter is None
    assert room.monster_level == 0
    assert 1 not in game.player.treasures_found
    assert not any(
        e.text and ("You found" in e.text or "You find" in e.text) for e in events
    )
