import random

from dungeon.generation import generate_dungeon, validate_dungeon


def test_generation_invariants():
    rng = random.Random(0)
    dungeon = generate_dungeon(rng)
    errors = validate_dungeon(dungeon)
    assert errors == []
