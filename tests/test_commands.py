import random

from dungeon.constants import Feature, Race, Spell
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
    session = game._encounter_session
    assert session is not None
    session.vitality = 0
    session._handle_monster_death([])
    assert 1 in game.player.treasures_found


def test_spell_clamping_never_increases_vitality():
    game = _make_game(7)
    room = game._current_room()
    room.monster_level = 1
    game._enter_room()
    session = game._encounter_session
    assert session is not None
    game.player.iq = 18
    before = session.vitality
    session._cast_spell(Spell.FIREBALL)
    assert session.vitality <= before

    game = _make_game(8)
    room = game._current_room()
    room.monster_level = 1
    game._enter_room()
    session = game._encounter_session
    assert session is not None
    game.player.iq = 18
    before = session.vitality
    session._cast_spell(Spell.LIGHTNING)
    assert session.vitality <= before
