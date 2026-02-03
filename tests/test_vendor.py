import random

from dungeon.constants import Feature, Race
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


def test_vendor_requires_b():
    game = _make_game(3)
    result = game.step("B")
    events = result.events
    assert any("no vendor" in e.text.lower() for e in events)


def test_vendor_entry_no_prompt():
    game = _make_game(4)
    room = game._current_room()
    room.feature = Feature.VENDOR
    room.monster_level = 0
    events = game._enter_room()
    assert game._shop_session is None
    assert any("vendor" in e.text.lower() for e in events)


def test_vendor_starts_session_with_letter_prompt():
    game = _make_game(10)
    room = game._current_room()
    room.feature = Feature.VENDOR
    game._enter_room()

    result = game.step("B")

    assert game._shop_session is not None
    prompt = next((e for e in result.events if e.kind == "PROMPT"), None)
    assert prompt is not None
    keys = [opt["key"] for opt in prompt.data["options"]]
    assert keys == ["W", "A", "S", "P", "F"]
