# Dungeon of Doom — Python Implementation Specification (v1.0)

This document defines the **idiomatic Python architecture** for implementing the Dungeon of Doom rules.
It is intended to be used as the scaffold contract for an IDE agent (e.g., Codex in VS Code).

Scope:
- Clean, maintainable Python implementation
- Engine/UI separation
- Unit-testable core logic
- Deterministic behavior **per environment** via `random.Random(seed)`

Non-goals:
- Cross-language RNG parity with a future C/6502 port
- Performance optimization

---

## 1. Repository Layout

```text
dungeon/
  src/dungeon/
    __init__.py
    constants.py
    types.py
    model.py
    generation.py
    engine.py
    ui_terminal.py
  tests/
    test_generation.py
    test_flares.py
    test_encounter.py
    test_vendor.py
    test_commands.py
  pyproject.toml
  README.md
```

### Module responsibilities
- `constants.py`: enums, command sets, display symbols/tables
- `types.py`: `Event`, `StepResult`, and other shared types
- `model.py`: dataclasses (`Room`, `Dungeon`, `Player`, etc.)
- `generation.py`: dungeon generation routines + invariant validation helpers
- `engine.py`: rules + state machine; **no printing**
- `terminal.py`: terminal I/O loop; formatting + prompts only

---

## 2. Constants and Enums (`constants.py`)

Use `Enum` for the following:

- `Feature`: `EMPTY, MIRROR, SCROLL, CHEST, FLARES, POTION, VENDOR, THIEF, WARP, STAIRS_UP, STAIRS_DOWN, EXIT`
- `Race`: `HUMAN, DWARF, ELF, HALFLING`
- `Spell`: `PROTECTION, FIREBALL, LIGHTNING, WEAKEN, TELEPORT`
- `Mode`: `EXPLORE, ENCOUNTER, GAME_OVER, VICTORY`

Also define:
- single-letter command sets (explore vs encounter)
- monster name table by level
- treasure name list (10)
- vendor price tables (weapons/armor: 10 / 20 / 30)

---

## 3. Core Model (`model.py`)

Use `@dataclass` for model objects.

### Suggested dataclasses

```python
from dataclasses import dataclass, field
from dungeon.constants import Feature, Spell

@dataclass
class Room:
    feature: Feature = Feature.EMPTY
    monster_level: int = 0      # 0 or 1..10
    treasure_id: int = 0        # 0 or 1..10
    seen: bool = False

@dataclass
class Dungeon:
    rooms: list[list[list[Room]]]  # rooms[z][y][x], axes 0..6

@dataclass
class Player:
    # Location (0-based)
    z: int
    y: int
    x: int

    # Stats
    str_: int
    dex: int
    iq: int
    hp: int
    mhp: int

    # Economy & inventory
    gold: int
    flares: int
    treasures_found: set[int] = field(default_factory=set)

    # Equipment
    weapon_tier: int = 0       # 0..3
    armor_tier: int = 0        # 0..3
    weapon_name: str = "none"
    armor_name: str = "none"
    armor_damaged: bool = False

    # Spell charges
    spells: dict[Spell, int] = field(default_factory=dict)

    # Encounter flags
    fatigued: bool = False
    temp_armor_bonus: int = 0  # protection spell bonus during encounter

    # Vendor-related
    attr_potion_target: str | None = None  # "STR"/"DEX"/"IQ"/"MHP"
```

### Encounter state
Keep encounter state separate from `Room`:

```python
@dataclass
class Encounter:
    monster_level: int
    monster_name: str
    vitality: int
```

---

## 4. Engine Events (`types.py`)

Engine emits structured events. UI renders them.

```python
from dataclasses import dataclass, field
from typing import Any
from dungeon.constants import Mode

@dataclass
class Event:
    kind: str                 # "INFO" | "ERROR" | "COMBAT" | "LOOT" | ...
    text: str
    data: dict[str, Any] = field(default_factory=dict)

@dataclass
class StepResult:
    events: list[Event]
    mode: Mode
    needs_input: bool         # whether UI should prompt again immediately
```

Rule: **engine never prints**.

---

## 5. Dungeon Generation (`generation.py`)

### API
```python
import random
from dungeon.model import Dungeon

def generate_dungeon(rng: random.Random) -> Dungeon:
    ...
```

### Representation
Use a 7×7×7 nested list of `Room` objects: `rooms[z][y][x]`.

### Generation rules (derived from the game spec)
- Initialize all rooms empty/unseen.
- Populate base distribution (features/monsters) per the rules spec.
- Place aligned stairs up/down for floors 1..6.
- Place exit on floor 7.
- Place exactly 10 treasures (allow treasure+monster co-location).

### Invariant validation helper
```python
def validate_dungeon(d: Dungeon) -> list[str]:
    """Return a list of invariant violations (empty list means OK)."""
```

---

## 6. Game Engine (`engine.py`)

### Public API
```python
import random
from dungeon.constants import Mode
from dungeon.types import StepResult

class Game:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.dungeon = generate_dungeon(self.rng)
        self.player = ...  # created via startup flow
        self.mode = Mode.EXPLORE
        self.encounter = None  # Encounter | None

    def step(self, command: str) -> StepResult:
        """Advance game state by one command."""

    def prompt(self) -> str:
        """Return the current input prompt string."""
```

### Parsing
- commands are **single-letter**, **case-insensitive**
- ignore leading/trailing whitespace
- in EXPLORE mode: interpret by explore command set
- in ENCOUNTER mode: interpret by encounter command set

### Room entry effects
On entering a cell:
- mark it `seen`
- if warp: relocate immediately (random floor + random cell) and then resolve new cell
- if thief: steal gold and clear feature
- if flare pickup: increment flares and clear feature
- if monster: start encounter and switch to ENCOUNTER
- chest damage marks armor as damaged for display; tier/defense stays the same

### Vendor modernization
- entering vendor does **not** prompt
- `B` opens shop only if in vendor room
- `0` exits shop at any stage (category/item/attribute)

### Exit logic
- `X` only works on EXIT room
- win only if all treasures found

### Encounter loop
- Fight / Run / Spell
- Run:
  - 40% success: relocate to random different cell on same floor; end encounter
  - 60% fail: set `player.fatigued=True`; continue encounter
- Spell eligibility:
  - IQ >= 12
  - charge > 0

### Spell clamping (agreed fix)
- Fireball damage: `d = max(rand(1..5) - (iq // 3), 0)`
- Lightning damage: `d = max(rand(1..10) - (iq // 2), 0)`

---

## 7. Startup Flow

Keep startup prompting in UI. Provide pure validation helpers in engine/module functions.

Suggested function signature:

```python
import random
from dungeon.constants import Race
from dungeon.model import Player

def create_player(
    rng: random.Random,
    race: Race,
    allocations: dict[str, int],
    weapon_tier: int,
    armor_tier: int,
    flare_count: int,
) -> Player:
    ...
```

UI responsibilities:
- ask race
- show rolled stats
- allocate +5 points with cap 18
- apply starting gold constraints to purchases

---

## 8. Terminal UI (`terminal.py`)

### API
```python
def run() -> None:
    ...
```

Responsibilities:
- prompt for seed
- run main loop
- render `Event`s
- prompt for command
- in ENCOUNTER, show encounter prompt (Fight/Run/Spell) but still accept single-letter commands
- status report is always displayed as part of the terminal UI
- support `/save [path]` and `/load [path]` (pickle `Game`), plus `--continue [path]` on startup (default `game.sav`)

---

## 9. Tests (`tests/`)

Minimum tests:
- generation invariants: exit count, stair alignment, 10 treasures
- flare reveal: corner/edge/center
- run behavior: fatigued blocks run; success relocates; fail sets fatigued
- warp: immediate relocation can change floors
- treasure+monster: treasure awarded only on kill
- spell clamping: fireball/lightning never increase monster vitality
- vendor modernization: no forced prompt; `B` requires vendor

---

## 10. Tooling

Recommended:
- `pytest`
- `ruff` (lint + format)
- type hints throughout

---

This Python implementation spec is intended to be used alongside the game rules spec as the authoritative scaffold contract.
