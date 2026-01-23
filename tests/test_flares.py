import random

from dungeon.constants import Race
from dungeon.engine import Game, create_player


def test_flare_reveal_neighbors():
    rng = random.Random(1)
    player = create_player(
        rng=rng,
        race=Race.HUMAN,
        allocations={"STR": 2, "DEX": 2, "IQ": 1},
        weapon_tier=1,
        armor_tier=1,
        flare_count=1,
    )
    game = Game(seed=1, player=player, rng=rng)
    game.player.z = 0
    game.player.y = 3
    game.player.x = 3

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            game.dungeon.rooms[0][3 + dy][3 + dx].seen = False

    game._use_flare()

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            assert game.dungeon.rooms[0][3 + dy][3 + dx].seen is True
