"""Original Arena (竞技场) progression built from the 1.20.4 tables.

The arena event scripts drive the UI/fight flow:

    openui uiid=10 par1=<arenaId> par2=<1 fresh | 2 continue>
    closeui yes -> fight type=3 npcid=<arenaId>
    fightover win -> openui par2=2, lose -> end

This module only owns the data side (rank, title, streak, opponent and the
ArenaNpcPet -> BattlePet conversion); the event runtime owns the actual flow.
"""
from __future__ import annotations

import json

from game_state import numbers


class ArenaProgress:
    def __init__(self, state):
        self.state = state
        self.tables = state.tables

    # -- state ---------------------------------------------------------------
    def _fields(self):
        if not hasattr(self.state, 'arena_ranks'):
            self.state.arena_ranks = {}
        if not hasattr(self.state, 'arena_titles'):
            self.state.arena_titles = {}
        if not hasattr(self.state, 'arena_wins'):
            self.state.arena_wins = {}
        if not hasattr(self.state, 'arena_streak'):
            self.state.arena_streak = {}
        return (self.state.arena_ranks, self.state.arena_titles,
                self.state.arena_wins, self.state.arena_streak)

    def arena(self, arena_id):
        row = self.tables['Arena'].get(str(arena_id))
        if not row:
            raise KeyError(f'原版 Arena 表没有竞技场 {arena_id}')
        return row

    def rank(self, arena_id):
        return int(self._fields()[0].get(str(arena_id), 101))

    def title_id(self, arena_id):
        return int(self._fields()[1].get(str(arena_id), 0) or 0)

    def title_name(self, arena_id):
        title = self.tables['ArenaTitle'].get(str(self.title_id(arena_id)))
        return title['name'] if title else '暂无称号'

    def streak(self, arena_id):
        return int(self._fields()[3].get(str(arena_id), 0) or 0)

    def wins(self, arena_id):
        return int(self._fields()[2].get(str(arena_id), 0) or 0)

    # -- opponent selection --------------------------------------------------
    def opponents(self, arena_id):
        rows = [r for r in self.tables['ArenaNpc'].values()
                if str(r.get('arenaId')) == str(arena_id)]
        def bounds(row):
            values = numbers(row.get('rankInterval'))
            if not values:
                return (999, 999)
            return (min(values), max(values))
        return sorted(rows, key=lambda r: (bounds(r), int(r['keyId'])))

    def next_npc(self, arena_id):
        """Pick the rank immediately above the player, matching rankInterval.

        A fresh player starts at rank 101; rank 100 is the first target.  Each
        win moves one rank up.  If a table gap exists, choose the closest lower
        interval instead of inventing an opponent.
        """
        rank = self.rank(arena_id)
        target = max(1, rank-1)
        rows = self.opponents(arena_id)
        for row in rows:
            values = numbers(row.get('rankInterval'))
            if values and min(values) <= target <= max(values):
                return row
        lower = [r for r in rows if numbers(r.get('rankInterval'))
                 and max(numbers(r.get('rankInterval'))) < rank]
        if lower:
            return max(lower, key=lambda r: max(numbers(r.get('rankInterval'))))
        return rows[-1] if rows else None

    def entry_cost(self, arena_id):
        """The first fight in a session costs a badge; consecutive wins do not."""
        if self.streak(arena_id) > 0:
            return None
        row = self.arena(arena_id)
        return str(row['moneyType']), int(row['moneyCount'])

    def can_enter(self, arena_id):
        cost = self.entry_cost(arena_id)
        if not cost:
            return True, ''
        money_type, amount = cost
        if self.state.count(money_type) < amount:
            name = (self.tables['Money'].get(money_type) or
                    self.tables['Item'].get(money_type) or {}).get('name', money_type)
            return False, f'{name}不足，需要 {amount} 个。'
        return True, ''

    # -- mutations -----------------------------------------------------------
    def enter(self, arena_id):
        """Charge a fresh-session entry.  Call inside the host transaction."""
        ok, reason = self.can_enter(arena_id)
        if not ok:
            raise ValueError(reason)
        cost = self.entry_cost(arena_id)
        if cost:
            self.state.consume([cost[0]], [cost[1]])

    def leave(self, arena_id):
        if hasattr(self.state, 'arena_streak'):
            self.state.arena_streak[str(arena_id)] = 0

    def finish(self, arena_id, npc_id, result):
        """Apply an arena result after the battle and return a small summary."""
        row = self.tables['ArenaNpc'].get(str(npc_id))
        if not row:
            raise KeyError(f'原版 ArenaNpc 表没有对手 {npc_id}')
        ranks, titles, wins, streaks = self._fields()
        aid = str(arena_id)
        summary = {'result': result, 'arena': aid, 'npc': str(npc_id),
                   'rank_before': self.rank(arena_id), 'rank_after': self.rank(arena_id),
                   'title': self.title_name(arena_id), 'drops': []}
        with self.state.transaction():
            if result not in ('win', 'caught'):
                streaks[aid] = 0
                return summary
            ranks[aid] = max(1, int(ranks.get(aid, 101))-1)
            streaks[aid] = int(streaks.get(aid, 0))+1
            wins[aid] = int(wins.get(aid, 0))+1
            # A title is displayed only for the boss/rank-title fights in the
            # original tables.  Normal opponents still carry a titleId for UI
            # text, but they do not take the player's title row.
            if str(row.get('isBoss')) == '1' and str(row.get('titleId', '0')) != '0':
                titles[aid] = int(row['titleId'])
            ids = numbers(row.get('dropItemIds'))
            counts = numbers(row.get('dropItemCounts'))
            for item, count in zip(ids, counts):
                if str(item) != '0' and count > 0:
                    self.state.grant(item, count)
                    summary['drops'].append([str(item), int(count)])
            summary['rank_after'] = self.rank(arena_id)
            summary['title'] = self.title_name(arena_id)
        return summary


def arena_pet_spec(tables, key, level):
    row = tables['ArenaNpcPet'].get(str(key))
    if not row:
        raise KeyError(f'原版 ArenaNpcPet 表没有配置 {key}')
    return {
        'species': str(row['petId']),
        'level': int(level),
        'skills': [str(v) for v in numbers(row.get('skills', '0'))],
        'talents': [str(v) for v in numbers(row.get('talents', '0'))],
        'variation': json.loads(row['attVar']),
        'growth': json.loads(row['attUp']),
    }


def make_arena_battle(tables, player_pets, arena_id, rng, rank=101):
    """Build the Battle for one arena rank.

    The event script passes the arena id as npcid for type=3 fights.  The
    concrete opponent row is selected from the player's saved rank.
    """
    from battle import Battle

    progress = ArenaProgress(_StateView(tables))
    progress.state.arena_ranks[str(arena_id)] = int(rank)
    npc = progress.next_npc(arena_id)
    if not npc:
        raise ValueError(f'竞技场 {arena_id} 没有可挑战的 ArenaNpc')
    pet_ids = numbers(npc.get('petIds'))
    count = max(1, int(npc.get('petCount', 1) or 1))
    if len(pet_ids) > count:
        pet_ids = rng.sample(pet_ids, count)
    elif not pet_ids:
        raise ValueError(f'竞技场对手 {npc["keyId"]} 没有宠物配置')
    specs = [arena_pet_spec(tables, key, npc['petLevel']) for key in pet_ids[:count]]
    title = tables['ArenaTitle'].get(str(npc.get('titleId', '0')))
    name = title['name'] if title else '竞技场对手'
    battle = Battle(tables, player_pets, specs, rng, kind='arena',
                    name=name, fight_row=npc, bgm='0',
                    can_catch=False, can_escape=False)
    battle.arena_id = str(arena_id)
    battle.arena_npc_id = str(npc['keyId'])
    battle.arena_title = name
    return battle


class _StateView:
    """Minimal duck-typed state used only for opponent selection in a factory."""

    def __init__(self, tables):
        self.tables = tables
        self.arena_ranks = {}
        self.arena_titles = {}
        self.arena_wins = {}
        self.arena_streak = {}