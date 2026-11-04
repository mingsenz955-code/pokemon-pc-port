"""Build pets from the original probability tables instead of inventing attributes."""
from __future__ import annotations

import json
import math
import random

from game_state import Pet, numbers
from game_formulas import add, sub, mul, f32


def _rows(value):
    return json.loads(value)


def weighted_choice(rng: random.Random, values, weights):
    values, weights = list(values), [float(w) for w in weights]
    if not values or len(values) != len(weights):
        raise ValueError('Invalid original probability vector lengths')
    if any(not math.isfinite(w) or w < 0 for w in weights):
        raise ValueError('Invalid original probability weight')
    total = sum(weights)
    if total <= 0:
        raise ValueError('Original probability vector has no positive weight')
    roll = rng.random()*total
    upto = 0.0
    for value, weight in zip(values, weights):
        upto += max(0, float(weight))
        if roll < upto:
            return value
    return values[-1]


def _attribute_roll(rng, intervals, probabilities):
    interval = weighted_choice(rng, intervals, probabilities)
    low, high = float(interval[0]), float(interval[1])
    # getFloatValueWithIntervalList (0x2ba826) uses an unsigned 32-bit
    # draw scaled by 2^-32, then binary32 multiply/add. It never rounds to
    # tenths; that old approximation materially changed pet attributes.
    fraction = mul(rng.getrandbits(32), 2**-32)
    return add(low, mul(fraction, sub(high, low)))


def generate_pet(tables, rng: random.Random, species, level=None, *, row=None, fixed_attributes=None):
    """Replicates the data-driven random pet generation exposed by the tables.

    The interval/probability columns are the original ones.  The exact original
    call order of the shared RNG is not recoverable from static data, so callers
    that need reproducible encounters pass their own seeded Random instance.
    """
    species = str(species)
    pet = tables['Pet'][species]
    probability_row = row if row is not None else pet
    if level is None:
        level = 1
    level = max(1, min(int(level), int(pet['maxLevel'])))
    if fixed_attributes is not None:
        variations, growth = ([f32(v) for v in values] for values in fixed_attributes)
        if len(variations) != 5 or len(growth) != 5:
            raise ValueError('Invalid fixed hatch attributes')
    else:
        variations = []
        for intervals, chances in zip(_rows(probability_row['attVarInterval']), _rows(probability_row['attVarIntPro'])):
            variations.append(_attribute_roll(rng, intervals, chances))
        growth = []
        for intervals, chances in zip(_rows(probability_row['attUpVarInterval']), _rows(probability_row['attUpVarIntPro'])):
            growth.append(_attribute_roll(rng, intervals, chances))

    pool = numbers(probability_row['talentIds'])
    weights = numbers(probability_row['talentProbability'])
    count_choices = numbers(probability_row['talentNum'])
    count_weights = numbers(probability_row['talentNumPro'])
    if len(count_choices) > 1 and len(count_weights) == 1:
        # X 2.10.9 row 101025 carries a count choice list but one shared
        # probability.  The original table is malformed, not a PC reason to
        # crash a battle; reuse the sole weight for each authored choice.
        count_weights *= len(count_choices)
    elif len(count_weights) > 1 and len(count_choices) == 1:
        count_choices *= len(count_weights)
    count = int(weighted_choice(rng, count_choices, count_weights)) if pool else 0
    count = min(count, len(pool))
    talents = []
    candidates = list(zip(pool, weights if len(weights) == len(pool) else [1]*len(pool)))
    for _ in range(count):
        if not candidates:
            break
        chosen = weighted_choice(rng, [c[0] for c in candidates], [c[1] for c in candidates])
        talents.append(chosen)
        candidates = [c for c in candidates if c[0] != chosen]

    skills = []
    for skill, unlock in zip(numbers(pet['skillIds']), numbers(pet['skillOepnLevel'])):
        if level >= unlock:
            skills.append(str(skill))
    skills = skills[-4:]

    result = Pet(species, level, variations, growth, skills, talents,
                 held_item='0')
    result.heal(tables)
    result.update_quality(tables)
    return result
