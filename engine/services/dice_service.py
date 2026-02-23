import random
import re
from typing import List, Tuple


def parse_dice_expr(expr: str) -> List[Tuple[int, int, int]]:
    """Parse dice expression into list of (count, sides, modifier)."""
    expr = expr.strip().replace(" ", "")

    pattern = r'^(\d*)d(\d+)([+-]\d+)?$'
    match = re.match(pattern, expr, re.IGNORECASE)

    if not match:
        raise ValueError(f"Invalid dice expression: {expr}")

    count_str, sides_str, mod_str = match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(mod_str) if mod_str else 0

    if count < 1:
        raise ValueError(f"Die count must be at least 1: {expr}")
    if sides < 2:
        raise ValueError(f"Die sides must be at least 2: {expr}")

    return [(count, sides, modifier)]


def roll_dice(expr: str) -> Tuple[int, str]:
    """Roll dice and return (result, breakdown)."""
    parts = parse_dice_expr(expr)
    count, sides, modifier = parts[0]

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    rolls_str = str(rolls[0]) if len(rolls) == 1 else str(rolls)

    if modifier > 0:
        breakdown = f"{expr}: {rolls_str}+{modifier}={total}"
    elif modifier < 0:
        breakdown = f"{expr}: {rolls_str}{modifier}={total}"
    else:
        breakdown = f"{expr}: {rolls_str}={total}"

    return total, breakdown
