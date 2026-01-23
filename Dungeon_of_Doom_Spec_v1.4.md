
# Dungeon of Doom — Technical Specification (v1.4)

This document defines the authoritative rules and architecture for the **Dungeon of Doom** project.
It supports:
- a Python reference implementation, and
- a later port to a restricted C subset suitable for 6502 cross-compilation.

All mechanics are derived from the original Atari BASIC implementation, with agreed fixes and modernizations.

---

## 1. Objective and End Conditions

- Dungeon size: **7 floors**, each **7×7**.
- Start: floor 1, cell 25 (center).
- Treasures: exactly **10**.

**Win**
- Collect all 10 treasures.
- Use `X` while standing in the Exit room on floor 7.

**Early Exit**
- Allowed, but treated as an incomplete run.

**Loss**
- HP ≤ 0.

---

## 2. Coordinates

- Floor `P`: 1..7
- Cell `P2`: 1..49

Conversions:
- `x = (P2 - 1) // 7 + 1`
- `y = P2 - (x - 1) * 7`
- `P2 = (x - 1) * 7 + y`

---

## 3. Cell Data

Each cell stores:
- `feature`
- `monster_level` (0 or 1..10)
- `treasure_id` (0 or 1..10)
- `seen` (bool)

Display precedence: **monster > treasure > feature**.

---

## 4. Commands (single-letter, case-insensitive)

Movement:
- N S E W
- U (stairs up only)
- D (stairs down only)

World:
- M map
- F flare
- X exit (exit room only)

Interaction:
- L mirror
- O chest
- R scroll
- P potion
- B buy (vendor only)

Info:
- T status
- H help

Encounter-only:
- F fight
- R run
- S spell

---

## 5. Visibility

- Entering a cell marks it seen.
- Map shows only current floor.
- Unseen cells show `?`.

### Flares
- Consume 1 flare.
- Reveal 8 neighboring cells on same floor.

---

## 6. Room Features

- Mirror: visions via `L`.
- Scroll: `R` grants random spell charge.
- Chest: `O` → trap / empty / gold.
- Flares pickup: auto +1..5 flares.
- Potion room: `P` drinks potion.
- Vendor: use `B` to buy.
- Thief: steals gold.
- Warp: immediate random relocation.
- Stairs: informational.
- Exit: informational.

---

## 7. Character Creation

Random rolls:
- RN, RD, RA ∈ 0..4
- R2 ∈ 0..6

| Race | STR | DEX | IQ | HP |
|-----|-----|-----|----|----|
| Human | 8+RN | 8+RD | 8+RA | 20+R2 |
| Dwarf | 10+RN | 8+RD | 6+RA | 22+R2 |
| Elf | 6+RN | 9+RD | 10+RA | 16+R2 |
| Halfling | 6+RN | 10+RD | 9+RA | 18+R2 |

- MHP = HP
- Allocate 5 points among STR/DEX/IQ (cap 18).

Starting gold: 50–60.

---

## 8. Dungeon Generation

- 70% empty cells.
- Otherwise may contain features or monsters.

Treasures:
- Place exactly 10.
- May coexist with monsters.

Stairs:
- One aligned stair per floor pair.

Exit:
- One Exit on floor 7.

---

## 9. Encounters

Monster vitality:
- `MV = 3*level + rand(0..3)`

Fight:
- Hit: `AS = 20 + 5*(11-level) + DX + 3*W`
- Damage: `MD = max(W + floor(STR/3) + rand(0..4) - 2, 1)`
- 5% weapon break chance.

Monster attack:
- Dodge: `20 + 5*(11-level) + 2*DX`
- Damage: `DD = max(rand(0..level-1) + 3 - A, 0)`

Run:
- 40% success → random cell same floor.
- 60% fail → fatigued.

Spells (IQ ≥ 12):
1. Protection (+3 armor temporarily)
2. Fireball: `max(rand(1..5) - floor(IQ/3), 0)`
3. Lightning: `max(rand(1..10) - floor(IQ/2), 0)`
4. Weaken: halve MV
5. Teleport: random cell same floor

Rewards:
- Treasure if present.
- Else gold: `5*level + rand(0..20)`

---

## 10. Vendors

Sell:
- Weapons, Armor, Spells, Potions

Prices:
- Weapons/Armor: 50 / 100 / 150
- Spells: Protection 50, Fireball 30, Lightning 50, Weaken 75, Teleport 80
- Potions: Healing 50, Attribute Enhancer 100

Attribute enhancer allows selecting stat to affect.

---

## 11. Portability Constraints

- Integer-only math
- Deterministic RNG
- Fixed-size arrays
- No dynamic allocation
- Engine/UI separation

This document is the authoritative reference.
