from __future__ import annotations

import random

from dungeon.constants import Feature
from dungeon.model import Dungeon, Room

_SIZE = 7


def generate_dungeon(rng: random.Random) -> Dungeon:
    rooms = [
        [[_create_room(rng, z) for _x in range(_SIZE)] for _y in range(_SIZE)]
        for z in range(_SIZE)
    ]
    _place_treasures(rng, rooms)
    _place_stairs(rng, rooms)
    _place_exit(rng, rooms)
    return Dungeon(rooms=rooms)


def _create_room(rng: random.Random, floor: int) -> Room:
    room = Room()
    if rng.random() > 0.3:
        roll = rng.randint(1, 10)
        if roll > 8:
            min_level = floor + 1
            max_level = min(10, min_level + 5)
            room.monster_level = rng.randint(min_level, max_level)
        else:
            room.feature = Feature(roll)
    return room


def _place_treasures(rng: random.Random, rooms: list[list[list[Room]]]) -> None:
    placed = 0
    while placed < 10:
        z = rng.randrange(_SIZE)
        y = rng.randrange(_SIZE)
        x = rng.randrange(_SIZE)
        room = rooms[z][y][x]
        if room.treasure_id != 0:
            continue
        if room.feature != Feature.EMPTY:
            continue
        placed += 1
        room.treasure_id = placed


def _place_stairs(rng: random.Random, rooms: list[list[list[Room]]]) -> None:
    for z in range(_SIZE - 1):
        while True:
            y = rng.randrange(_SIZE)
            x = rng.randrange(_SIZE)
            room = rooms[z][y][x]
            room_below = rooms[z + 1][y][x]
            if room.treasure_id > 0 or room.monster_level > 0:
                continue
            if room_below.treasure_id > 0 or room_below.monster_level > 0:
                continue
            if room.feature == Feature.STAIRS_DOWN:
                continue
            room.feature = Feature.STAIRS_UP
            room_below.feature = Feature.STAIRS_DOWN
            break


def _place_exit(rng: random.Random, rooms: list[list[list[Room]]]) -> None:
    z = _SIZE - 1
    while True:
        y = rng.randrange(_SIZE)
        x = rng.randrange(_SIZE)
        room = rooms[z][y][x]
        if room.treasure_id > 0 or room.monster_level > 0:
            continue
        if room.feature in {Feature.STAIRS_UP, Feature.STAIRS_DOWN, Feature.EXIT}:
            continue
        room.feature = Feature.EXIT
        break


def validate_dungeon(dungeon: Dungeon) -> list[str]:
    errors: list[str] = []
    if len(dungeon.rooms) != _SIZE:
        return ["Dungeon has incorrect number of floors."]

    exit_count = 0
    treasure_count = 0
    stairs_up_counts = [0] * _SIZE
    stairs_down_counts = [0] * _SIZE

    for z in range(_SIZE):
        for y in range(_SIZE):
            if len(dungeon.rooms[z][y]) != _SIZE:
                errors.append(f"Row size mismatch on floor {z}.")
            for x in range(_SIZE):
                room = dungeon.rooms[z][y][x]
                if room.feature == Feature.EXIT:
                    if z != _SIZE - 1:
                        errors.append("Exit placed on non-final floor.")
                    exit_count += 1
                if room.treasure_id:
                    treasure_count += 1
                    if room.feature != Feature.EMPTY:
                        errors.append("Treasure placed in non-empty room.")
                if room.monster_level > 0 and room.feature != Feature.EMPTY:
                    errors.append("Monster placed in room with feature.")
                if room.feature == Feature.STAIRS_UP:
                    stairs_up_counts[z] += 1
                    if z == _SIZE - 1:
                        errors.append("Stairs up on final floor.")
                    elif dungeon.rooms[z + 1][y][x].feature != Feature.STAIRS_DOWN:
                        errors.append("Stair alignment mismatch.")
                if room.feature == Feature.STAIRS_DOWN:
                    stairs_down_counts[z] += 1
                    if z == 0:
                        errors.append("Stairs down on first floor.")
                    elif dungeon.rooms[z - 1][y][x].feature != Feature.STAIRS_UP:
                        errors.append("Stair alignment mismatch.")
                if room.feature in {Feature.EXIT, Feature.STAIRS_UP, Feature.STAIRS_DOWN}:
                    if room.monster_level > 0 or room.treasure_id > 0:
                        errors.append("Feature placed in room with monster or treasure.")

    for z in range(_SIZE):
        if z < _SIZE - 1 and stairs_up_counts[z] != 1:
            errors.append("Floor must contain exactly one staircase up.")
        if z == _SIZE - 1 and stairs_up_counts[z] != 0:
            errors.append("Final floor must not contain staircase up.")
        if z > 0 and stairs_down_counts[z] != 1:
            errors.append("Floor must contain exactly one staircase down.")
        if z == 0 and stairs_down_counts[z] != 0:
            errors.append("First floor must not contain staircase down.")

    if exit_count != 1:
        errors.append("Dungeon must contain exactly one exit.")
    if treasure_count != 10:
        errors.append("Dungeon must contain exactly 10 treasures.")

    return errors
