import random

from dungeon.constants import Feature, Race, Spell
from dungeon.engine import Game, create_player
from dungeon.model import Encounter


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


def test_warp_relocates():
    game = _make_game(5)
    game.rng = random.Random(5)
    room = game._current_room()
    room.feature = Feature.WARP
    start = (game.player.z, game.player.y, game.player.x)
    game._enter_room()
    end = (game.player.z, game.player.y, game.player.x)
    assert end != start


def test_treasure_awarded_on_kill():
    game = _make_game(6)
    room = game._current_room()
    room.treasure_id = 1
    room.monster_level = 1
    game._enter_room()
    assert 1 not in game.player.treasures_found
    game.encounter.vitality = 0
    game._handle_monster_death()
    assert 1 in game.player.treasures_found


def test_spell_clamping_never_increases_vitality():
    game = _make_game(7)
    game.encounter = Encounter(monster_level=1, monster_name="Skeleton", vitality=10)
    game.player.iq = 18
    before = game.encounter.vitality
    game._cast_spell(Spell.FIREBALL)
    assert game.encounter is None or game.encounter.vitality <= before

    game.encounter = Encounter(monster_level=1, monster_name="Skeleton", vitality=10)
    before = game.encounter.vitality
    game._cast_spell(Spell.LIGHTNING)
    assert game.encounter is None or game.encounter.vitality <= before
