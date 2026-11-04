"""PetItem recovery parameters shared by party and battle item use.

Types/attribute IDs come from the original table, corroborated by Item.des.
Integer percentage truncation follows PetDataManager::addAttributePercent at
ARM address 0x3260e0 (multiply then integer division by 100).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Recovery:
    hp: int
    energy: int
    cleanse: bool = False


def recovery(row, hp, energy, max_hp, max_energy):
    kind = int(row['type'])
    if kind == 4:
        return Recovery(hp, energy, True)
    if kind not in (1, 2, 3):
        raise ValueError(f'PetItem type {kind} is not a recovery effect')
    if hp <= 0 and kind != 3:
        raise ValueError('宠物已死亡，请使用复活石。')
    if hp > 0 and kind == 3:
        raise ValueError('这只宠物不需要复活。')
    parameters = [int(value) for value in str(row['parameters']).split(',')]
    if not parameters or len(parameters) % 2:
        raise ValueError('Invalid original PetItem parameter pairs')
    values, maximums = {1: hp, 2: energy}, {1: max_hp, 2: max_energy}
    for attribute, amount in zip(parameters[::2], parameters[1::2]):
        if attribute not in values or amount < 0:
            raise ValueError('Invalid original PetItem recovery attribute or amount')
        recovered = amount if kind == 1 else maximums[attribute]*amount//100
        values[attribute] = min(maximums[attribute], values[attribute]+recovered)
    if kind == 3:
        values[1] = max(1, values[1])
    return Recovery(values[1], values[2])
