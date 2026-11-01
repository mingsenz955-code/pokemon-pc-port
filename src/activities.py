"""Native activities recovered from 1.20.4 tables and ARM call sequences.

See docs/MECHANICS_EVIDENCE.md for verified rules and remaining differences.
No network, payment SDK, or Android executable is loaded by this module.
"""
from datetime import datetime, timedelta, timezone
import time
import json
from dataclasses import asdict

from game_state import numbers, Pet
from pet_factory import generate_pet, weighted_choice
from daily_tasks import DailyTasks


class Activities:
    def __init__(self, state):
        self.state = state

    def open_village_chest(self, key):
        key = str(key)
        row = self.state.tables['VillageChest'][key]
        with self.state.transaction():
            opened = self.state.activities.setdefault('village_chests', [])
            if key in opened:
                raise ValueError('这个宝箱已经打开过了。')
            self.state.grant_many(numbers(row['itemIds']), numbers(row['itemCounts']))
            opened.append(key)
        return list(zip(numbers(row['itemIds']), numbers(row['itemCounts'])))

    def put_egg(self, index, item):
        item = str(item)
        if type(index) is not int or index not in range(10):
            raise ValueError('请选择 1–10 号孵化位。')
        if item not in self.state.tables['HatchItem']:
            raise ValueError('请选择原版宠物蛋。')
        with self.state.transaction():
            eggs = self.state.activities.setdefault('eggs', {})
            if str(index) in eggs:
                raise ValueError('这个孵化位已有宠物蛋。')
            self.state.consume([item], [1])
            eggs[str(index)] = {'item': item, 'exp': 0, 'pet': None}

    def add_hatch_exp(self, amount):
        if type(amount) is not int or amount < 0:
            raise ValueError('Invalid hatch experience')
        for egg in self.state.activities.get('eggs', {}).values():
            if egg['pet'] is None:
                maximum = int(self.state.tables['HatchItem'][egg['item']]['exp'])
                egg['exp'] = min(maximum, egg['exp']+amount)

    def hatch(self, index, *, use_money=False):
        with self.state.transaction():
            egg = self.state.activities.get('eggs', {}).get(str(index))
            if not egg or egg['pet'] is not None:
                raise ValueError('这个位置没有待孵化的蛋。')
            row = self.state.tables['HatchItem'][egg['item']]
            if use_money:
                self.state.consume([row['moneyId']], [int(row['moneyCount'])])
            else:
                if egg['exp'] < int(row['exp']):
                    raise ValueError('孵化经验不足。')
                self.state.consume(numbers(row['itemIds']), numbers(row['itemCounts']))
            ids = numbers(row['petIds'])
            picked = weighted_choice(self.state.rng, list(range(len(ids))), numbers(row['probabilitys'], float))
            fixed = None
            if int(row['random']) == 0:
                fixed = (json.loads(row['attVar'])[picked], json.loads(row['attUp'])[picked])
            pet = generate_pet(self.state.tables, self.state.rng, ids[picked], 1, fixed_attributes=fixed)
            egg['pet'], egg['exp'] = asdict(pet), 0
        return pet

    def take_egg(self, index):
        with self.state.transaction():
            eggs = self.state.activities.get('eggs', {})
            egg = eggs.get(str(index))
            if not egg:
                raise ValueError('这个孵化位是空的。')
            if egg['pet'] is None:
                self.state.grant(egg['item'], 1)
                result = None
            else:
                result = Pet(**egg['pet'])
                self.state.receive_pet(result)
            del eggs[str(index)]
        return result

    def start_cards(self):
        state = self.state
        previous = state.activities.get('cards')
        if previous and (previous['result'] is None or
                         previous['result'] == 1 and not previous.get('claimed')):
            raise ValueError('请先完成当前牌局并领取奖励。')
        row = state.tables['CardLegend']['1']
        groups = {star: [key for key, pet in state.tables['Pet'].items()
                         if int(pet['starLevel']) == star] for star in range(1, 6)}
        with state.transaction():
            state.consume(['220008'], [1])
            def deal():
                hand = []
                for _ in range(5):
                    star = weighted_choice(state.rng, list(range(1, 6)), numbers(row['cardPros'], float))
                    hand.append({'species': state.rng.choice(groups[star]), 'star': star})
                return hand
            match = {'player': deal(), 'enemy': deal(), 'used': [], 'enemy_used': [],
                     'score': [0, 0], 'round': 1, 'result': None, 'reward': None,
                     'claimed': False, 'history': []}
            match['enemy_index'] = state.rng.randrange(5)
            state.activities['cards'] = match
        return match

    def play_card(self, index):
        state = self.state
        match = state.activities.get('cards')
        if not match or match['result'] is not None:
            raise ValueError('当前没有进行中的牌局。')
        if type(index) is not int or index not in range(5) or index in match['used']:
            raise ValueError('请选择尚未使用的手牌。')
        with state.transaction():
            enemy = match['enemy_index']
            ours, theirs = match['player'][index]['star'], match['enemy'][enemy]['star']
            if ours != theirs:
                match['score'][0 if ours > theirs else 1] += 1
            match['used'].append(index)
            match['enemy_used'].append(enemy)
            match['history'].append({'player': index, 'enemy': enemy, 'stars': [ours, theirs]})
            left = 5-match['round']
            first, second = match['score']
            if first > 2 or first > second+left:
                match['result'] = 1
            elif first == second and left == 0:
                match['result'] = 0
            elif second > 2 or second > first+left:
                match['result'] = -1
            else:
                match['round'] += 1
                match['enemy_index'] = state.rng.choice([i for i in range(5) if i not in match['enemy_used']])
            if match['result'] == 1:
                row = state.tables['CardLegend']['1']
                ids, counts = numbers(row['itemIds']), numbers(row['itemCounts'])
                weights = numbers(row['probabilitys'], float)
                if not len(ids) == len(counts) == len(weights):
                    raise ValueError('Invalid original CardLegend reward pool')
                reward = weighted_choice(state.rng, list(range(len(ids))), weights)
                match['reward'] = {'item': str(ids[reward]), 'count': counts[reward]}
        if match['result'] == 1:
            DailyTasks(state).record('cards_win')
        return match

    def claim_cards(self):
        match = self.state.activities.get('cards')
        if not match or match['result'] != 1:
            raise ValueError('只有胜利牌局可以领取奖励。')
        if match['claimed']:
            return None
        with self.state.transaction():
            reward = match['reward']
            self.state.grant(reward['item'], reward['count'])
            match['claimed'] = True
        return reward

    def draw_pets(self, kind, *, free=False, now=None):
        kind = int(kind)
        if kind not in (1, 2, 3):
            raise ValueError('Unknown original LuckyDraw ID')
        state = self.state
        now = int(time.time() if now is None else now)
        row = state.tables['LuckyDraw'][str(kind)]
        count = 3 if kind == 3 else 1
        if state.pet_free_slots() < count:
            raise ValueError('宠物背包和银行没有足够空位。')
        if free:
            if kind != 1:
                raise ValueError('只有普通抽宠支持免费次数。')
            ready = int(state.activities.get('lucky_free_at', 0))
            if now < ready:
                raise ValueError(f'免费抽宠还需等待 {ready-now} 秒。')
        store = state.tables['Store'][str(70600+kind)]
        with state.transaction():
            if not free:
                state.consume([store['costMoneyType']], [int(store['costCount'])])
            pets = []
            for index in range(count):
                rare = kind == 3 and index == 0
                species = weighted_choice(state.rng,
                    numbers(row['rarePetIds' if rare else 'petIds']),
                    numbers(row['rareProbabilitys' if rare else 'probabilitys'], float))
                pet = generate_pet(state.tables, state.rng, species, 1, row=row)
                state.receive_pet(pet)
                pets.append(pet)
            if free:
                state.activities['lucky_free_at'] = now+int(row['freeTime'])
            state.activities['lucky_draw_count'] = state.activities.get('lucky_draw_count', 0)+count
        return pets

    def roulette_board(self, *, now=None, paid_refresh=False):
        state = self.state
        now = int(time.time() if now is None else now)
        previous = int(state.activities.get('roulette_refreshed_at', 0))
        zone = timezone(timedelta(hours=8))
        day = lambda timestamp: datetime.fromtimestamp(timestamp, zone).date()
        board = state.activities.get('roulette_board', [])
        if board and not paid_refresh and day(now) <= day(previous):
            return board
        with state.transaction():
            if paid_refresh:
                state.consume(['700002'], [1])
            board = []
            for key in sorted(state.tables['LuckyRoulette'], key=int):
                row = state.tables['LuckyRoulette'][key]
                ids, amounts = numbers(row['itemIds']), numbers(row['itemCounts'])
                weights = numbers(row['probabilitys'], float)
                if not len(ids) == len(amounts) == len(weights):
                    raise ValueError('Invalid original roulette reward pool')
                for _ in range(int(row['boxCount'])):
                    index = weighted_choice(state.rng, list(range(len(ids))), weights)
                    board.append({'item': str(ids[index]), 'count': amounts[index],
                                  'weight': int(row['hitPro']), 'group': str(key)})
            # Original refreshItems performs 100 random transpositions, moving
            # item/count/hit-weight together, rather than shuffling each vector.
            for _ in range(100):
                first = state.rng.randrange(len(board))
                second = state.rng.randrange(len(board))
                board[first], board[second] = board[second], board[first]
            state.activities['roulette_board'] = board
            state.activities['roulette_refreshed_at'] = now
        return board

    def spin_roulette(self, *, now=None):
        state = self.state
        with state.transaction():
            state.consume(['220009'], [1])
            board = self.roulette_board(now=now)
            index = weighted_choice(state.rng, list(range(len(board))), [r['weight'] for r in board])
            reward = board[index]
            state.grant(reward['item'], reward['count'])
            state.activities['roulette_count'] = state.activities.get('roulette_count', 0)+1
            state.activities['roulette_last_index'] = index
        DailyTasks(state).record('roulette')
        return index, reward
