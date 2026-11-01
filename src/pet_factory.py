"""Build pets from the original probability tables instead of inventing attributes."""
from __future__ import annotations

import json
import random

from game_state import Pet, numbers


def _rows(value):
    return json.loads(value)


def weighted_choice(rng: random.Random, values, weights):
    total = sum(max(0, float(w)) for w in weights)
    if total <= 0:
        return values[rng.randrange(len(values))]
    roll = rng.random()*total
    upto = 0.0
    for value, weight in zip(values, weights):
        upto += max(0, float(weight))
        if roll <= upto:
            return value
    return values[-1]


def _attribute_roll(rng, intervals, probabilities):
    interval = weighted_choice(rng, intervals, probabilities)
    low, high = float(interval[0]), float(interval[1])
    if high <= low:
        return round(low, 1)
    return round(rng.uniform(low, high), 1)


def generate_pet(tables, rng: random.Random, species, level=None, *, row=None):
    """Replicates the data-driven random pet generation exposed by the tables.

    The interval/probability columns are the original ones.  The exact original
    call order of the shared RNG is not recoverable from static data, so callers
    that need reproducible encounters pass their own seeded Random instance.
    """
    species = str(species)
    pet = tables['Pet'][species]
    if level is None:
        level = 1
    level = max(1, min(int(level), int(pet['maxLevel'])))
    variations = []
    for intervals, chances in zip(_rows(pet['attVarInterval']), _rows(pet['attVarIntPro'])):
        variations.append(_attribute_roll(rng, intervals, chances))
    growth = []
    for intervals, chances in zip(_rows(pet['attUpVarInterval']), _rows(pet['attUpVarIntPro'])):
        growth.append(_attribute_roll(rng, intervals, chances))

    pool = numbers(pet['talentIds'])
    weights = numbers(pet['talentProbability'])
    count_choices = numbers(pet['talentNum'])
    count_weights = numbers(pet['talentNumPro'])
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
    return result