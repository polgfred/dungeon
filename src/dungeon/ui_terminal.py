from __future__ import annotations

import random

from dungeon.constants import Mode, Race
from dungeon.engine import Game, create_player, roll_base_stats
from dungeon.types import Event


def run() -> None:
    print("Dungeon of Doom")
    print()
    seed = _prompt_int("Seed", default=0)
    rng = random.Random(seed)
    print()
    race = _prompt_race()

    rng_state = rng.getstate()
    base_str, base_dex, base_iq, base_hp = roll_base_stats(rng, race)
    print()
    print("Thy characteristics are as follows:")
    print(f" Strength     {base_str}")
    print(f" Dexterity    {base_dex}")
    print(f" Intelligence {base_iq}")
    print(f" Hit points   {base_hp}")

    print()
    allocations = _prompt_allocations()
    gold = rng.randint(50, 60)
    print()
    weapon_tier = _prompt_purchase("weapon", gold)
    gold -= _price_weapon(weapon_tier)
    print()
    armor_tier = _prompt_purchase("armor", gold)
    gold -= _price_armor(armor_tier)
    print()
    flare_count = _prompt_int(
        "Flares (1 gold each)", default=0, min_value=0, max_value=gold
    )
    gold -= flare_count

    rng.setstate(rng_state)
    player = create_player(
        rng=rng,
        race=race,
        allocations=allocations,
        weapon_tier=weapon_tier,
        armor_tier=armor_tier,
        flare_count=flare_count,
    )

    game = Game(seed=seed, player=player, rng=rng)
    print()
    print("The dungeon awaits you...")
    _render_events(game.start_events())

    prompt = "F/R/S> " if game.mode == Mode.ENCOUNTER else "--> "
    while True:
        print()
        command = input(prompt)
        result = game.step(command)
        _render_events(result.events)
        if result.mode.name in {"GAME_OVER", "VICTORY"}:
            break
        prompt = result.prompt or "--> "


def _render_events(events: list[Event]) -> None:
    for event in events:
        match event.kind:
            case "MAP":
                for row in event.data.get("grid", []):
                    print(row)
            case "STATUS":
                data = event.data
                print("--------------------------------------")
                print(f"GOLD - {data['gold']}       TREASURES - {data['treasures']}")
                print(f"FLARES - {data['flares']}")
                print(f"PROTECTIONS - {data['protection']}")
                print(
                    f"FIREBALLS - {data['fireball']}      LIGHTNINGS - {data['lightning']}"
                )
                print(
                    f"WEAKENINGS - {data['weaken']}       TELEPORTS - {data['teleport']}"
                )
                print(
                    f"You have {data['armor']} armour and your weapon is a {data['weapon']}."
                )
                print("--------------------------------------")
            case "PROMPT":
                print(event.text)
                if event.data:
                    print(
                        f"1> Protection {event.data['protection']}  2> Fireball {event.data['fireball']}  "
                        f"3> Lightning {event.data['lightning']}  4> Weaken {event.data['weaken']}  "
                        f"5> Teleport {event.data['teleport']}"
                    )
            case "INFO" | "ERROR" | "COMBAT" | "LOOT":
                if event.text:
                    print(event.text)
            case _:
                if event.text:
                    print(event.text)


def _prompt_race() -> Race:
    while True:
        print("Choose thy race:")
        print("  1> Human")
        print("  2> Dwarf")
        print("  3> Elf")
        print("  4> Halfling")
        choice = input("Which one? ").strip()
        if choice in {"1", "2", "3", "4"}:
            return Race(int(choice))
        print("I don't understand that.")


def _prompt_allocations() -> dict[str, int]:
    remaining = 5
    allocations = {}
    for key in ("STR", "DEX", "IQ"):
        while True:
            print(f"You have {remaining} points.")
            value = _prompt_int(
                f"Points to add to {key}", default=0, min_value=0, max_value=remaining
            )
            allocations[key] = value
            remaining -= value
            break
    if remaining != 0:
        print("Allocations must total 5 points.")
        return _prompt_allocations()
    return allocations


def _prompt_purchase(kind: str, gold: int) -> int:
    label = "weapon" if kind == "weapon" else "armor"
    while True:
        print(f"You have {gold} gold pieces.")
        if kind == "weapon":
            print("  1> Dagger 10")
            print("  2> Short sword 20")
            print("  3> Broadsword 30")
        else:
            print("  1> Leather 10")
            print("  2> Wooden 20")
            print("  3> Chain mail 30")
        choice = input(f"Which {label}? ").strip()
        if choice not in {"1", "2", "3"}:
            print("I don't understand that.")
            continue
        tier = int(choice)
        price = _price_weapon(tier) if kind == "weapon" else _price_armor(tier)
        if price > gold:
            print("Don't try to cheat me. It won't work!")
            continue
        return tier


def _price_weapon(tier: int) -> int:
    return {1: 10, 2: 20, 3: 30}[tier]


def _price_armor(tier: int) -> int:
    return {1: 10, 2: 20, 3: 30}[tier]


def _prompt_int(
    label: str,
    *,
    default: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    while True:
        prompt = f"{label}"
        if default is not None:
            prompt += f" [{default}]"
        prompt += ": "
        raw = input(prompt).strip()
        if not raw and default is not None:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                print("Enter a number.")
                continue
        if min_value is not None and value < min_value:
            print(f"Minimum is {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"Maximum is {max_value}.")
            continue
        return value


if __name__ == "__main__":
    run()
