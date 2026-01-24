# Dungeon of Doom

Dungeon of Doom is a small, turn-based dungeon crawler. You explore a 7-floor maze, fight monsters, collect treasures, and decide when to press deeper or retreat.

## How to Play

1. Start the game and choose a seed, race, and starting gear.
2. Explore rooms, gather treasures, and survive encounters.
3. Find all 10 treasures, reach the exit on floor 7, and use `X` to win.

## Controls

Commands are single letters and are case-insensitive.

Movement:
- `N` `S` `E` `W` move
- `U` stairs up (only in a stairs-up room)
- `D` stairs down (only in a stairs-down room)

World:
- `M` map of the current floor
- `F` flare (reveals nearby rooms)
- `X` exit (only in the exit room)

Interaction:
- `L` look in mirror
- `O` open chest
- `R` read scroll
- `P` drink potion
- `B` buy from vendor

Info:
- `H` help

Encounter-only:
- `F` fight
- `R` run
- `S` cast spell (choose from the spell list)

## What to Expect

- Rooms may contain features, monsters, or treasure.
- Monsters trigger an encounter where you can fight, run, or cast spells.
- Scrolls grant spell charges. Spells can protect you, deal damage, weaken foes, or teleport you.
- Vendors sell better gear, scrolls, and potions.
- Flares reveal nearby rooms on your current floor.

## Saving and Loading

During play, use:
- `/save [path]` to save (defaults to `game.sav`)
- `/load [path]` to load (defaults to `game.sav`)

## Map Legend

When exploring, the map uses:
- `*` you
- `?` unknown
- `M` monster
- `T` treasure
- `0` empty
- `m` mirror
- `s` scroll
- `c` chest
- `f` flares
- `p` potion
- `v` vendor
- `t` thief
- `w` warp
- `U` stairs up
- `D` stairs down
- `X` exit
