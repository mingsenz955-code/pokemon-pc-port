"""Original Budokan (道馆试练) progression from the 1.20.4 tables.

The event scripts use the trial-tower UI (uiid 15) as the gym trial gate:

    openui uiid=15 par1=<budokanId>
    closeui yes -> fight type=4 npcid=<budokanId>
    fightover win -> openui uiid=15 again, lose -> end

For type=4, ``npcid`` is the Budokan id, not an NpcFight id.  Each Budokan
owns twenty ordered BudokanNpc rows; only the next row can be challenged.
A win advances that gym's persisted counter and grants the row's configured
drops.  The twentieth opponent is the only one carrying the gym's evolution
material, so it is granted exactly once by the normal battle reward path.
"""
from __future__ import annotations

import json

from game_state import numbers


class BudokanProgress:
    def __init__(self, state):
        self.state = state
        self.tables = state.tables

    def _fields(self):
        # Init.budokanLevels is serialized as GameState.budokans; use the
        # original field instead of inventing a parallel activity counter.
        if not hasattr(self.state, 'budokans'):
            self.state.budokans = {}
        return self.state.budokans

    def gym(self, budokan_id):
        row = self.tables.get('Budokan', {}).get(str(budokan_id))
        if not row:
            raise KeyError(f'原版 Budokan 表没有道馆 {budokan_id}')
        return row

    def opponents(self, budokan_id):
        ids = numbers(self.gym(budokan_id).get('npcIds'))
        rows = []
        for npc_id in ids:
            row = self.tables.get('BudokanNpc', {}).get(str(npc_id))
            if not row:
                raise KeyError(f'原版 BudokanNpc 表没有 {npc_id}')
            rows.append(row)
        return rows

    def wins(self, budokan_id):
        return int(self._fields().get(str(budokan_id), 0) or 0)

    def total(self, budokan_id):
        return len(numbers(self.gym(budokan_id).get('npcIds')))

    def complete(self, budokan_id):
        return self.wins(budokan_id) >= self.total(budokan_id)

    def next_npc(self, budokan_id):
        rows = self.opponents(budokan_id)
        index = self.wins(budokan_id)
        return rows[index] if index < len(rows) else None

    def finish(self, budokan_id, npc_id, result):
        """Record one completed trial battle; only a win advances."""
        before = self.wins(budokan_id)
        npc = self.next_npc(budokan_id)
        if npc is None:
            raise ValueError(f'原版 {self.gym(budokan_id)["name"]} 二十场试练已经完成')
        if str(npc['keyId']) != str(npc_id):
            raise ValueError('试练对手与当前进度不一致，不能伪造下一场')
        after = before
        if result == 'win':
            with self.state.transaction():
                self._fields()[str(budokan_id)] = before+1
            after = before+1
        return {
            'budokan_id': str(budokan_id),
            'npc_id': str(npc_id),
            'npc_name': npc.get('name', str(npc_id)),
            'result': result,
            'before': before,
            'after': after,
            'total': self.total(budokan_id),
            'complete': after >= self.total(budokan_id),
        }


def budokan_pet_spec(tables, key):
    row = tables.get('BudokanNpcPet', {}).get(str(key))
    if not row:
        raise KeyError(f'原版 BudokanNpcPet 表没有配置 {key}')
    return {
        'species': str(row['petId']),
        'level': int(row['level']),
        'skills': [str(v) for v in numbers(row.get('skills', '0'))],
        'talents': [str(v) for v in numbers(row.get('talents', '0'))],
        'variation': json.loads(row['attVar']),
        'growth': json.loads(row['attUp']),
    }


def make_budokan_battle(tables, player_pets, budokan_id, npc_id, rng):
    """Build one gym trial Battle from BudokanNpc/BudokanNpcPet."""
    from battle import Battle

    npc = tables['BudokanNpc'].get(str(npc_id))
    if not npc:
        raise KeyError(f'原版 BudokanNpc 表没有 {npc_id}')
    keys = numbers(npc.get('petIds'))
    if not keys:
        raise ValueError(f'BudokanNpc {npc_id} 没有宠物配置')
    specs = [budokan_pet_spec(tables, key) for key in keys]
    # BudokanNpc rows do not serialize dropPros, but the original gym gives
    # its configured reward on each victory.  Mark those drops as guaranteed
    # so Battle.apply_rewards remains the single atomic reward path.
    row = dict(npc)
    ids = numbers(row.get('dropItemIds', '0'))
    counts = numbers(row.get('dropItemCounts', '0'))
    row['dropPros'] = ','.join('100' for _ in ids) if ids else '0'
    row['dropItemCounts'] = ','.join(str(v) for v in counts) if counts else '0'
    battle = Battle(tables, player_pets, specs, rng, kind='budokan',
                    name=npc.get('name', '道馆试练'), fight_row=row,
                    bgm='0', can_catch=False, can_escape=False)
    battle.budokan_id = str(budokan_id)
    battle.budokan_npc_id = str(npc_id)
    return battle