"""Infinite Arena (无限竞技场) from the original IArena tables.

Event contract (pEventTalk790101 / pEventTalk30523):

    openui 19 -> closeui yes -> tomap exit=790102      (info screen)
    openui 20 -> closeui yes -> fight type=5 npcid=1   (guard confirm)
    fightover win -> talk, lose -> talk + tomap

`npcid=1` is the InfiniteArena id, not the floor.  The floor is persisted in
`infinite_level` and chooses one IArenaNpc row (Lv.30/60/90/120/121).
"""
from __future__ import annotations

import json

from game_state import numbers


class InfiniteArenaProgress:
    def __init__(self, state):
        self.state = state
        self.tables = state.tables

    def _ensure(self):
        if not hasattr(self.state, 'infinite_level'):
            self.state.infinite_level = 1
        if not hasattr(self.state, 'infinite_highest'):
            self.state.infinite_highest = 1
        if not hasattr(self.state, 'infinite_honor'):
            self.state.infinite_honor = 0

    def arena(self, arena_id):
        row = self.tables['InfiniteArena'].get(str(arena_id))
        if not row:
            raise KeyError(f'原版 InfiniteArena 表没有竞技场 {arena_id}')
        return row

    def level(self, arena_id='1'):
        self._ensure()
        return max(1, min(self.max_level(), int(self.state.infinite_level)))

    def max_level(self):
        return max(1, len(self.levels()))

    def highest(self):
        self._ensure()
        return int(self.state.infinite_highest)

    def honor(self):
        self._ensure()
        return int(self.state.infinite_honor)

    def state_value(self, arena_id='1'):
        return int(self.state.arenas.get(str(arena_id), 0))

    def levels(self):
        rows = [r for r in self.tables['IArenaNpc'].values()
                if str(r.get('arenaId', '1')) == '1']
        return sorted(rows, key=lambda r: (int(r['petLevel']), int(r['keyId'])))

    def level_row(self, arena_id='1', level=None):
        rows = self.levels()
        if not rows:
            raise ValueError('原版 IArenaNpc 表为空')
        index = self.level(arena_id) if level is None else int(level)
        return rows[max(0, min(len(rows)-1, index-1))]

    def entry_cost(self, arena_id='1'):
        row = self.arena(arena_id)
        return str(row['moneyType']), int(row['moneyCount'])

    def can_enter(self, arena_id='1'):
        money, amount = self.entry_cost(arena_id)
        if self.state.count(money) < amount:
            name = (self.tables['Money'].get(money) or
                    self.tables['Item'].get(money) or {}).get('name', money)
            return False, f'{name}不足，需要 {amount} 个。'
        return True, ''

    def enter(self, arena_id='1'):
        ok, reason = self.can_enter(arena_id)
        if not ok:
            raise ValueError(reason)
        money, amount = self.entry_cost(arena_id)
        self.state.consume([money], [amount])

    def finish(self, result, arena_id='1'):
        self._ensure()
        summary = {'result': result, 'level_before': self.level(arena_id),
                   'level_after': self.level(arena_id), 'honor_before': self.honor(),
                   'honor_after': self.honor(), 'highest': self.highest()}
        with self.state.transaction():
            if result not in ('win', 'caught'):
                self.state.arenas[str(arena_id)] = 0
                return summary
            # Formula_InfiniteArenaHonorReward always returns 1 in 1.20.4.
            self.state.infinite_honor += 1
            self.state.grant('700007', 1)
            self.state.arenas[str(arena_id)] = 1
            before = self.level(arena_id)
            self.state.infinite_level = min(self.max_level(), before+1)
            self.state.infinite_highest = max(self.highest(), self.state.infinite_level)
            summary['level_after'] = self.level(arena_id)
            summary['honor_after'] = self.honor()
            summary['highest'] = self.highest()
        return summary


def infinite_pet_spec(tables, key, level, rng):
    row = tables['IArenaNpcPet'].get(str(key))
    if not row:
        raise KeyError(f'原版 IArenaNpcPet 表没有配置 {key}')
    talents = []
    pool = [str(v) for v in numbers(row.get('talentIds', '0'))]
    if pool:
        counts = numbers(row.get('talentNum', '0')) or [1, 1]
        count = rng.randint(min(counts), max(counts))
        probabilities = numbers(row.get('talentProbability', '0'))
        if len(probabilities) == len(pool):
            talents = rng.choices(pool, weights=probabilities, k=count)
        else:
            talents = rng.sample(pool, min(count, len(pool)))
    return {
        'species': str(row['petId']),
        'level': int(level),
        'skills': [str(v) for v in numbers(row.get('skills', '0'))],
        'talents': talents,
        'variation': json.loads(row['attVar']),
        'growth': json.loads(row['attUp']),
    }


def make_infinite_arena_battle(tables, player_pets, arena_id, rng, level=None):
    from battle import Battle
    row = InfiniteArenaProgress(_StateView(tables)).level_row(arena_id, level)
    pool = []
    for field in ('petAIds', 'petBIds', 'petCIds'):
        pool.extend(str(v) for v in numbers(row.get(field, '0')))
    pool = list(dict.fromkeys(pool))
    if not pool:
        raise ValueError(f'无限竞技场第 {level or "?"} 层没有宠物池')
    count = min(6, len(pool))
    keys = rng.sample(pool, count)
    specs = [infinite_pet_spec(tables, key, row['petLevel'], rng) for key in keys]
    battle = Battle(tables, player_pets, specs, rng, kind='infinite_arena',
                    name='无限竞技场守护者', fight_row=row, bgm='0',
                    can_catch=False, can_escape=False)
    battle.infinite_arena_id = str(arena_id)
    battle.infinite_level = int(level or 1)
    return battle


class _StateView:
    def __init__(self, tables):
        self.tables = tables
        self.arenas = {}
        self.infinite_level = 1
        self.infinite_highest = 1
        self.infinite_honor = 0