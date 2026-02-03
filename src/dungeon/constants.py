from __future__ import annotations

from enum import Enum


class Feature(Enum):
    EMPTY = 0
    MIRROR = 1
    SCROLL = 2
    CHEST = 3
    FLARES = 4
    POTION = 5
    VENDOR = 6
    THIEF = 7
    WARP = 8
    STAIRS_UP = 9
    STAIRS_DOWN = 10
    EXIT = 11


class Race(Enum):
    HUMAN = 1
    DWARF = 2
    ELF = 3
    HALFLING = 4


class Spell(Enum):
    PROTECTION = 1
    FIREBALL = 2
    LIGHTNING = 3
    WEAKEN = 4
    TELEPORT = 5


class Mode(Enum):
    EXPLORE = 1
    ENCOUNTER = 2
    GAME_OVER = 3
    VICTORY = 4


EXPLORE_COMMANDS = {
    "N",
    "S",
    "E",
    "W",
    "U",
    "D",
    "F",
    "X",
    "L",
    "O",
    "R",
    "P",
    "B",
    "H",
}
ENCOUNTER_COMMANDS = {"F", "R", "S"}

MONSTER_NAMES = [
    "Skeleton",
    "Goblin",
    "Kobold",
    "Orc",
    "Troll",
    "Werewolf",
    "Banshee",
    "Hellhound",
    "Chimaera",
    "Dragon",
]

TREASURE_NAMES = [
    "Gold Fleece",
    "Black Pearl",
    "Ruby Ring",
    "Diamond Clasp",
    "Silver Medallion",
    "Precious Spices",
    "Sapphire",
    "Golden Circlet",
    "Jeweled Cross",
    "Silmaril",
]

WEAPON_NAMES = ["(None)", "Dagger", "Short sword", "Broadsword"]
ARMOR_NAMES = ["(None)", "Leather", "Wooden", "Chain mail"]

WEAPON_PRICES = {1: 10, 2: 20, 3: 30}
ARMOR_PRICES = {1: 10, 2: 20, 3: 30}

SPELL_PRICES = {
    Spell.PROTECTION: 50,
    Spell.FIREBALL: 30,
    Spell.LIGHTNING: 50,
    Spell.WEAKEN: 75,
    Spell.TELEPORT: 80,
}

POTION_PRICES = {
    "HEALING": 50,
    "ATTRIBUTE": 100,
}

FEATURE_SYMBOLS = {
    Feature.EMPTY: "-",
    Feature.MIRROR: "m",
    Feature.SCROLL: "s",
    Feature.CHEST: "c",
    Feature.FLARES: "f",
    Feature.POTION: "p",
    Feature.VENDOR: "v",
    Feature.THIEF: "t",
    Feature.WARP: "w",
    Feature.STAIRS_UP: "U",
    Feature.STAIRS_DOWN: "D",
    Feature.EXIT: "X",
}
