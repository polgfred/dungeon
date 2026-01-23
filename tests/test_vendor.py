import random

from dungeon.constants import Feature, Race
from dungeon.engine import Game, create_player


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


def test_vendor_requires_b():
    game = _make_game(3)
    events = game._open_vendor()
    assert any("no vendor" in e.text.lower() for e in events)


def test_vendor_entry_no_prompt():
    game = _make_game(4)
    room = game._current_room()
    room.feature = Feature.VENDOR
    events = game._enter_room()
    assert game._shop_state is None
    assert any("vendor" in e.text.lower() for e in events)
