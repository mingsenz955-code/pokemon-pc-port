"""Persistent native game state, separate from the historical preview-position save."""
from __future__ import annotations

import copy
import json
import math
import os
import random
import uuid
from contextlib import contextmanager
from functools import wraps
from dataclasses import asdict, dataclass, field
from pathlib import Path

from game_formulas import add, attribute, level_exp, train_attribute, train_hp, train_mp
from economy import GOLD_PER_FEN, EVOLUTION_GOLD_COST


def numbers(value, cast=int):
    if isinstance(value, list):
        return [cast(v) for v in value]
    if not value or value == '0':
        return []
    return [cast(v) for v in str(value).split(',') if v.strip()]


def atomic_mutation(method):
    @wraps(method)
    def apply(self, *args, **kwargs):
        with self.transaction():
            return method(self, *args, **kwargs)
    return apply


@dataclass
class Pet:
    species: str
    level: int
    variation: list[float]
    growth: list[float]
    skills: list[str]
    talents: list[str]
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)
    hp: int = -1
    energy: int = -1
    exp: int = 0
    training: list[int] = field(default_factory=lambda: [0]*5)
    friendly: int = 0
    breakthrough: int = 0
    held_item: str = '0'
    quality: int = 1
    trial_id: str = ''
    trial_remaining: int = -1

    def update_quality(self, tables):
        total = 0.0
        for value in self.variation+self.growth:
            total = add(total, value)
        for key, row in tables.get('PetQuality', {}).items():
            low, high = numbers(row['attInterval'], float)
            if low <= total < high:
                self.quality = int(key)
                break
        return self.quality

    def stats(self, tables):
        base = numbers(tables['Pet'][self.species]['attributeBase'])[:5]
        result = [attribute(b, self.variation[i], self.growth[i], self.level, hp=i == 0)
                  for i, b in enumerate(base)]
        for i, amount in enumerate(self.training):
            result[i] += (train_hp if i == 0 else train_mp if i == 1 else train_attribute)(amount)
        if self.breakthrough:
            bonus = tables['PetTuPo'].get(str(self.breakthrough), {})
            for i, value in enumerate(numbers(bonus.get('attUp', '0'))[:5]):
                result[i] += value
        return result

    def heal(self, tables):
        stats = self.stats(tables)
        self.hp, self.energy = stats[:2]

    def add_exp(self, amount, tables):
        if amount < 0:
            raise ValueError('Experience cannot be negative')
        self.exp += amount
        changed = []
        maximum = int(tables['Pet'][self.species]['maxLevel'])
        while self.level < maximum and self.exp >= level_exp(self.level):
            self.exp -= level_exp(self.level)
            before = self.stats(tables)
            self.level += 1
            after = self.stats(tables)
            self.hp = max(0, min(after[0], self.hp+after[0]-before[0]))
            self.energy = max(0, min(after[1], self.energy+after[1]-before[1]))
            changed.append(self.level)
        return changed


class GameState:
    FORMAT = 'pocket-native-v2'

    @contextmanager
    def transaction(self):
        """Roll back failed state changes, including RNG and existing pet objects."""
        original = dict(self.__dict__)
        saved = {k: copy.deepcopy(v) for k, v in original.items()
                 if k not in {'tables', 'rng', 'pets', 'bank'}}
        teams = (list(self.pets), list(self.bank))
        pets = [(pet, copy.deepcopy(pet.__dict__)) for pet in self.pets+self.bank]
        random_state = self.rng.getstate()
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(original)
            for key, value in saved.items():
                current = self.__dict__[key]
                if isinstance(current, dict):
                    current.clear()
                    current.update(value)
                elif isinstance(current, list):
                    current[:] = value
                else:
                    self.__dict__[key] = value
            self.pets[:], self.bank[:] = teams
            for pet, values in pets:
                pet.__dict__.clear()
                pet.__dict__.update(values)
            self.rng.setstate(random_state)
            raise

    def grant_many(self, ids, amounts):
        ids, amounts = list(ids), list(amounts)
        if len(ids) != len(amounts):
            raise ValueError('Reward IDs and counts must have equal lengths')
        with self.transaction():
            for key, amount in zip(ids, amounts):
                self.grant(key, amount)

    def __init__(self, tables, seed=None):
        self.tables = tables
        self.rng = random.Random(seed)
        self.map_id, self.x, self.y = 7401, 17*64+32, 0
        self.initialization = 2
        self.starter_id = 0
        self.player_name = '皮尔'
        self.sprite_id = '20021'
        self.inventory = {}
        self.pets, self.bank = [], []
        self.active_pet = 0
        self.main_task, self.main_state = 1, 3
        self.branch_states = {}
        self.completed_main, self.completed_branch = [], []
        self.task_counts = {}
        self.events = {}
        self.npc_fights = {}
        self.functions = {}
        self.visible = {}
        self.positions = {}
        self.temp_npcs = {}
        self.areas = []
        self.visited_maps = []
        self.chests = []
        self.removed_obstacles = []
        self.encyclopedia = []
        self.seen_species = []
        self.budokans = {}
        self.arenas = {}
        self.arena_ranks = {}
        self.arena_titles = {}
        self.arena_wins = {}
        self.arena_streak = {}
        self.infinite_level = 1
        self.infinite_highest = 1
        self.infinite_honor = 0
        self.hatching = []
        self.rides, self.ride = [], 0
        self.trial_ride = 0
        self.world_focus = 7401
        self.story_ending = False
        self.pending_runtime = None
        self.presentation = {}
        self.activities = {}
        self.shop_purchases = {}
        self.last_rewards = []
        self.audit = []
        self.initialize(2)

    def preset_pet(self, key, table='InitPet'):
        row = self.tables[table][str(key)]
        pet = Pet(str(row['petId']), int(row['level']),
                  json.loads(row['attVar']), json.loads(row['attUp']),
                  [str(v) for v in numbers(row['skills'])],
                  [str(v) for v in numbers(row['talents'])], held_item=row.get('itemId', '0'))
        pet.heal(self.tables)
        pet.update_quality(self.tables)
        return pet

    def initialize(self, key):
        row = self.tables['Init'][str(key)]
        # initPlayer 0x331538..0x3315ae removes bag/bank pets and clears
        # owned rides and IllustratedStatus before granting the new preset.
        # The prologue's temporary team must not unlock the main hero's pets.
        self.bank = []
        self.active_pet = 0
        self.encyclopedia = []
        self.seen_species = []
        self.rides, self.ride = [], 0
        self.initialization = int(key)
        self.starter_id = 0
        self.player_name = '尼尔' if int(key) == 1 else '皮尔'
        self.sprite_id = row['spriteId']
        self.inventory = {str(k): n for k, n in zip(numbers(row['itemIds']), numbers(row['itemCounts']))}
        self.inventory['700004'] = 6
        self.pets = [self.preset_pet(k) for k in numbers(row['petIds'])]
        for p in self.pets:
            self.record_pet(p.species)
        self.budokans = {str(k): value for k, value in zip(numbers(row['budokanIds']), numbers(row['budokanLevels']))}
        self.arenas = {str(k): value for k, value in zip(numbers(row['arenaIds']), numbers(row['arenaTitles']))}
        arena_ids = numbers(row.get('arenaIds', ''))
        self.arena_ranks = {str(k): rank for k, rank in zip(arena_ids, numbers(row.get('arenaRanks', '')))}
        self.arena_titles = {str(k): title for k, title in zip(arena_ids, numbers(row.get('arenaTitles', '')))}
        self.arena_wins = {str(k): 0 for k in arena_ids}
        self.arena_streak = {str(k): 0 for k in arena_ids}
        self.infinite_level = 1
        self.infinite_highest = 1
        self.infinite_honor = 0

    def record_seen_pet(self, species):
        species = str(species)
        if species not in self.tables['Pet']:
            raise KeyError('原版宠物表中没有这个宠物。')
        if species not in self.seen_species:
            self.seen_species.append(species)

    def record_pet(self, species):
        self.record_seen_pet(species)
        if str(species) not in self.encyclopedia:
            self.encyclopedia.append(str(species))
        # Ride.petId connects captured/evolved/purchased pets to their mount.
        for key, row in self.tables.get('Ride', {}).items():
            if str(row['petId']) == str(species) and int(key) not in self.rides:
                self.rides.append(int(key))

    def main_matches(self, task_id, state):
        """TaskManager::compareMainTaskId: past=5, future=2; current exact."""
        task_id, state = int(task_id), int(state)
        if self.main_task == task_id:
            return self.main_state == state
        return state == (5 if self.main_task > task_id else 2)

    def branch_matches(self, task_id, state):
        return self.branch_states.get(str(task_id), 2) == int(state)

    def count(self, item_id):
        if str(item_id) == '700003':
            return self.inventory.get('700001', 0)//GOLD_PER_FEN
        return self.inventory.get(str(item_id), 0)

    def grant(self, item_id, amount):
        item_id, amount = str(item_id), int(amount)
        if item_id == '700003':
            item_id, amount = '700001', amount*GOLD_PER_FEN
        if item_id == '0' or amount == 0:
            return
        if amount < 0:
            raise ValueError('Use consume() for item removal')
        if item_id in self.tables['Pet']:
            for _ in range(amount):
                self.add_generated_pet(item_id)
            return
        if item_id not in self.tables['Item'] and item_id not in self.tables['Money']:
            raise KeyError(f'Unknown original item {item_id}')
        self.inventory[item_id] = min(6, self.count(item_id)+amount) if item_id == '700004' else self.count(item_id)+amount

    def add_generated_pet(self, species, level=1):
        """Original random attributes, generated from the Pet probability columns."""
        from pet_factory import generate_pet
        pet = generate_pet(self.tables, self.rng, species, level)
        self.receive_pet(pet)
        return pet

    def open_chest_item(self, item_id='210001'):
        """Original ChestItem 210001: consume the chest and its 240001 key."""
        item_id = str(item_id)
        row = self.tables.get('ChestItem', {}).get(item_id)
        if not row:
            raise ValueError('原版宝箱表中没有这个宝箱。')
        if self.count(item_id) <= 0:
            raise ValueError('没有可开启的宝箱。')
        cost_ids = [str(v) for v in numbers(row.get('costIds', ''))]
        cost_counts = [int(v) for v in numbers(row.get('costCounts', ''))]
        if len(cost_ids) != len(cost_counts):
            raise ValueError('原版宝箱消耗列不完整。')
        for key, count in zip(cost_ids, cost_counts):
            if self.count(key) < count:
                raise ValueError('缺少开启宝箱所需的钥匙。')
        ids = [str(v) for v in numbers(row.get('itemIds', ''))]
        probabilities = [int(v) for v in numbers(row.get('probabilitys', ''))]
        counts = [int(v) for v in numbers(row.get('itemCounts', ''))]
        if not ids or len(ids) != len(probabilities) or len(ids) != len(counts):
            raise ValueError('原版宝箱奖励列不完整。')
        picks = min(max(1, int(row.get('kindCount', 1))), len(ids))
        chosen = self.rng.choices(range(len(ids)), weights=probabilities, k=picks)
        rewards = [(ids[index], counts[index]) for index in chosen]
        with self.transaction():
            self.consume([item_id]+cost_ids, [1]+cost_counts)
            for key, count in rewards:
                self.grant(key, count)
        return rewards

    def pet_capacity(self, bank=False):
        key = '700005' if bank else '700004'
        return (self.count(key) if key in self.inventory else 200) if bank else 6

    def pet_free_slots(self):
        return max(0, self.pet_capacity()-len(self.pets))+max(0, self.pet_capacity(True)-len(self.bank))

    def receive_pet(self, pet):
        if len(self.pets) < self.pet_capacity():
            self.pets.append(pet)
        elif len(self.bank) < self.pet_capacity(True):
            self.bank.append(pet)
        else:
            raise ValueError('宠物背包和银行都已满。')
        if pet.trial_id:
            self.record_seen_pet(pet.species)
        else:
            self.record_pet(pet.species)

    def trial_pet_purchased(self, key):
        key = str(key)
        if key in self.activities.get('trial_purchased', {}):
            return True
        # Old releases cleared trial_id on purchase without keeping a receipt.
        # Recover those pets from the messenger's fixed attributes, not merely
        # from the species (a normally captured pet must not count as a purchase).
        row = self.tables['TrialPet'].get(key)
        if not row:
            return False
        species = str(row['petId'])
        lineage = {species}
        while species in self.tables['Evolution']:
            species = str(self.tables['Evolution'][species]['petId'])
            if species in lineage:
                break
            lineage.add(species)
        return any(not p.trial_id and p.species in lineage
                   and p.level >= int(row['level'])
                   and p.variation == json.loads(row['attVar'])
                   and p.growth == json.loads(row['attUp'])
                   and p.talents == [str(v) for v in numbers(row['talents'])]
                   for p in self.pets+self.bank)

    @atomic_mutation
    def receive_trial_pet(self, key):
        key = str(key)
        row = self.tables['TrialPet'].get(key)
        if self.trial_pet_purchased(key):
            raise ValueError('这只使者宠物已经永久购买，无需再次试用。')
        if not row or int(row['trialCount']) <= 0:
            raise ValueError('这只宠物没有免费试用次数。')
        if any(p.trial_id for p in self.pets+self.bank):
            raise ValueError('已经携带试用宠物，请先归还。')
        if key in self.activities.get('trial_received', []):
            raise ValueError('这只宠物的免费试用已经领取过。')
        if len(self.pets) >= self.pet_capacity():
            raise ValueError('携带宠物栏已满，请先到银行腾出位置。')
        pet = self.preset_pet(key, 'TrialPet')
        pet.trial_id, pet.trial_remaining = key, int(row['trialCount'])
        self.receive_pet(pet)
        self.active_pet = len(self.pets)-1
        self.activities.setdefault('trial_received', []).append(key)
        return pet

    def store_bought_out(self,key):
        from economy import store_limit_group
        row=self.tables['Store'][str(key)];group=store_limit_group(row)
        if group:
            return bool(self.shop_purchases.get('StoreLimit:'+group) or any(
                self.shop_purchases.get('Store:'+str(k),0)>0 and store_limit_group(r)==group
                for k,r in self.tables['Store'].items()))
        return row['repeat']=='0' and bool(self.shop_purchases.get('Store:'+str(key),0))

    @atomic_mutation
    def buy_store(self, key):
        row = self.tables['Store'][str(key)]
        if row['shopType'] not in ('1', '2', '7'):
            raise ValueError('请选择对应玩法中的商品。')
        if row['costMoneyType'] == '700001' and row['gotItemKid'] == '700001':
            raise ValueError('金币充值商品已移除，不能用金币购买金币。')
        purchase = 'Store:'+str(key)
        if self.store_bought_out(key):
            raise ValueError('这件限购商品已经购买过了。')
        rewards = (json.loads(row['items']) if row['items'] != '[]' else
                   [[row['gotItemKid'], int(row['gotCount'])]])
        if not rewards or any(str(k) == '0' or int(n) <= 0 for k, n in rewards):
            raise ValueError('这个商品没有可领取的奖励。')
        if all(str(k) == '700004' for k, _ in rewards) and self.pet_capacity() >= 6:
            raise ValueError('随身宠物栏已开放全部6格，无需再次购买。')
        self.consume([row['costMoneyType']], [int(row['costCount'])])
        for key_id, count in rewards:
            self.grant(key_id, count)
        self.shop_purchases[purchase] = self.shop_purchases.get(purchase, 0)+1
        from economy import store_limit_group
        group=store_limit_group(row)
        if group:self.shop_purchases['StoreLimit:'+group]=1
        spent = self.activities.setdefault('shop_spent', {})
        money = row['costMoneyType']
        spent[money] = int(spent.get(money, 0))+int(row['costCount'])
        from daily_tasks import DailyTasks
        DailyTasks(self).record('purchase')
        return [(str(k), int(n)) for k, n in rewards]

    @atomic_mutation
    def buy_trial_pet(self, key):
        key = str(key)
        if self.trial_pet_purchased(key):
            raise ValueError('这只使者宠物已经永久购买，不能重复购买。')
        row = self.tables['TrialPet'][key]
        store = self.tables['Store'][row['storeId']]
        current = next((p for p in self.pets+self.bank if p.trial_id == key), None)
        if not current and self.pet_free_slots() < 1:
            raise ValueError('宠物背包和银行都已满。')
        self.consume([store['costMoneyType']], [int(store['costCount'])])
        if current:
            pet = current
            pet.trial_id, pet.trial_remaining = '', -1
            self.record_pet(pet.species)
        else:
            pet = self.preset_pet(key, 'TrialPet')
            self.receive_pet(pet)
        self.activities.setdefault('trial_purchased', {})[key] = pet.uid
        if key not in self.activities.setdefault('trial_received', []):
            self.activities['trial_received'].append(key)
        return pet

    def move_pet(self, uid, *, to_bank):
        source, destination = (self.pets, self.bank) if to_bank else (self.bank, self.pets)
        pet = next((p for p in source if p.uid == uid), None)
        if pet is None:
            raise ValueError('找不到这只宠物。')
        if pet.trial_id:
            raise ValueError('试用宠物请在宠物使者处归还，不能存入银行。')
        if len(destination) >= self.pet_capacity(to_bank):
            raise ValueError('目标宠物格已满。')
        if to_bank and len(source) <= 1:
            raise ValueError('至少需要携带一只宠物。')
        source.remove(pet)
        destination.append(pet)
        self.active_pet = min(self.active_pet, max(0, len(self.pets)-1))

    def sync_pet_skills(self, pet):
        """Unlock original skills whose skillOepnLevel has been reached."""
        row = self.tables['Pet'][pet.species]
        unlocked = [str(skill) for skill, unlock in
                    zip(numbers(row['skillIds']), numbers(row['skillOepnLevel']))
                    if pet.level >= unlock]
        added = []
        for skill in unlocked:
            if skill not in pet.skills and len(pet.skills) < 4:
                pet.skills.append(skill)
                added.append(skill)
        return added

    @atomic_mutation
    def learn_skill(self, uid, skill_id, *, replace=None, scroll=None):
        pet = next((p for p in self.pets if p.uid == uid), None)
        if pet is None:
            raise ValueError('请选择携带的宠物。')
        skill_id = str(skill_id)
        passive = self.tables.get('Talent', {}).get(skill_id)
        if passive is not None:
            learned = [i for i, key in enumerate(pet.talents) if 400200 <= int(key) < 400300]
            if not 400200 <= int(skill_id) < 400300 or scroll is None:
                raise ValueError('被动技能需要对应的技能卷轴。')
            if skill_id in [str(k) for k in pet.talents]:
                raise ValueError('这只宠物已经学会该被动技能。')
            if replace is not None and (type(replace) is not int or replace not in range(len(learned))):
                raise ValueError('请选择要替换的后天被动技能。')
            if len(learned) >= 2 and replace is None:
                raise ValueError('两个后天被动技能已满，请选择一个替换。')
            if str(self.tables['SkillItem'].get(str(scroll), {}).get('skillId')) != skill_id:
                raise ValueError('技能卷轴与所选技能不符。')
            self.consume([str(scroll)], [1])
            if replace is None:
                pet.talents.append(skill_id)
            else:
                pet.talents[learned[replace]] = skill_id
            return skill_id
        skill = self.tables['Skill'].get(skill_id)
        if skill is None:
            raise ValueError('请选择原版主动技能。')
        if skill_id in pet.skills:
            raise ValueError('这只宠物已经学会该技能。')
        if replace is not None and (type(replace) is not int or replace not in range(len(pet.skills))):
            raise ValueError('请选择要替换的技能。')
        if len(pet.skills) >= 4 and replace is None:
            raise ValueError('技能已满，请选择一个技能替换。')
        if scroll is not None:
            scroll = str(scroll)
            if str(self.tables['SkillItem'].get(scroll, {}).get('skillId')) != skill_id:
                raise ValueError('技能卷轴与所选技能不符。')
            self.consume([scroll], [1])
        else:
            # The original paid tutor lists PetData::getSkillIds without a
            # level gate; level-based free learning is a separate event path.
            if skill_id not in [str(v) for v in numbers(self.tables['Pet'][pet.species]['skillIds'])]:
                raise ValueError('该宠物不能在技能师处学习此技能。')
            self.consume([skill['moneyId']], [int(skill['moneyCount'])])
        if replace is None:
            pet.skills.append(skill_id)
        else:
            pet.skills[replace] = skill_id
        return skill_id

    def consume(self, ids, amounts):
        ids, amounts = list(ids), list(amounts)
        if len(ids) != len(amounts):
            raise ValueError('Cost IDs and counts must have equal lengths')
        costs = {}
        for key, n in zip(ids, amounts):
            if str(key) == '700003':
                key, n = '700001', int(n)*GOLD_PER_FEN
            if str(key) != '0':
                if int(n) < 0:
                    raise ValueError('Negative item cost')
                costs[str(key)] = costs.get(str(key), 0)+int(n)
        if any(self.count(k) < n for k, n in costs.items()):
            raise ValueError('所需道具或货币不足')
        for key, amount in costs.items():
            self.inventory[key] = self.count(key)-amount

    @atomic_mutation
    def use_item(self, item_id, pet=None):
        from item_effects import recovery
        item_id = str(item_id)
        row = self.tables['Item'].get(item_id)
        if not row:
            raise ValueError('原版道具表中没有这个道具。')
        if int(row.get('useType', 0)) not in (1, 2):
            raise ValueError(f'{row.get("name", item_id)} 不是可在背包中使用的回复道具。')
        if self.count(item_id) <= 0:
            raise ValueError('道具数量不足。')
        effect = self.tables.get('PetItem', {}).get(item_id)
        if effect is not None and int(effect['type']) in (5, 6):
            kind, amount = int(effect['type']), int(effect['parameters'])
            if amount <= 0:
                raise ValueError('原版道具参数无效。')
            if pet is None:
                pet = next((p for p in self.pets if (p.friendly < 6 if kind == 5 else
                            p.level < int(self.tables['Pet'][p.species]['maxLevel']))), None)
            if pet is None or not any(p is pet for p in self.pets):
                raise ValueError('请选择可使用该道具的携带宠物。')
            if kind == 5:
                # PetDataManager::init 0x326466 initializes maxFriendly=6.
                if pet.friendly >= 6:
                    raise ValueError('该宠物的亲密度已经达到上限。')
                pet.friendly = min(6, pet.friendly+amount)
            else:
                maximum = int(self.tables['Pet'][pet.species]['maxLevel'])
                if pet.level >= maximum:
                    raise ValueError('该宠物已经达到原版等级上限。')
                before = pet.stats(self.tables)
                pet.level = min(maximum, pet.level+amount)
                pet.exp = 0
                self.sync_pet_skills(pet)
                after = pet.stats(self.tables)
                pet.hp = min(after[0], pet.hp+after[0]-before[0])
                pet.energy = min(after[1], pet.energy+after[1]-before[1])
            self.consume([item_id], [1])
            return f'{row["name"]} 已使用。'
        if effect is not None and int(effect['type']) == 7:
            attribute_id, amount = numbers(effect['parameters'])
            if not 1 <= attribute_id <= 5 or amount <= 0:
                raise ValueError('Invalid original training item parameters')
            index = attribute_id-1
            if pet is None:
                pet = next((p for p in self.pets if p.training[index] < 1000 and sum(p.training) < 2000), None)
            if pet is None or not any(p is pet for p in self.pets):
                raise ValueError('没有可训练的携带宠物。')
            gained = min(amount, 1000-pet.training[index], 2000-sum(pet.training))
            if gained <= 0:
                raise ValueError('该宠物已达到原版训练上限。')
            pet.training[index] += gained
            self.consume([item_id], [1])
            return f'{row["name"]} 已使用，训练值增加 {gained}。'
        if effect is None or int(effect['type']) not in (1, 2, 3):
            raise ValueError('该道具的宠物效果尚未接入，未消耗道具。')
        def needs_recovery(candidate):
            hp, energy = candidate.stats(self.tables)[:2]
            try:
                result = recovery(effect, candidate.hp, candidate.energy, hp, energy)
            except ValueError:
                return False
            return (result.hp, result.energy) != (candidate.hp, candidate.energy)
        if pet is None:
            pet = next((p for p in self.pets if needs_recovery(p)), None)
        if pet is None:
            raise ValueError('当前没有需要回复的宠物。')
        if not any(p is pet for p in self.pets):
            raise ValueError('只能对携带的宠物使用回复道具。')
        result = recovery(effect, pet.hp, pet.energy, *pet.stats(self.tables)[:2])
        if (result.hp, result.energy) == (pet.hp, pet.energy):
            raise ValueError('这只宠物不需要此道具回复。')
        pet.hp, pet.energy = result.hp, result.energy
        self.consume([item_id], [1])
        uses = dict(self.activities.get('heal_items', {}))
        uses[str(item_id)] = int(uses.get(str(item_id), 0))+1
        self.activities['heal_items'] = uses
        return f'{row.get("name", item_id)} 已用于 {self.tables["Pet"].get(str(pet.species), {}).get("name", pet.species)}。'

    def buy(self, table, key, quantity=1):
        if type(quantity) is not int or quantity <= 0:
            raise ValueError('Quantity must be positive')
        row = self.tables[table][str(key)]
        item_id = str(row['goodsKid'])
        cost = int(row['price'])*quantity
        if cost < 0:
            raise ValueError('Negative shop price')
        purchase_key = f'{table}:{key}'
        if str(row.get('repeat', '1')) == '0' and (
                quantity != 1 or self.shop_purchases.get(purchase_key, 0)):
            raise ValueError('这件商品只能兑换一次。')
        if self.count(row['moneyType']) < cost:
            raise ValueError('货币不足')
        with self.transaction():
            self.grant(item_id, quantity*int(row.get('gotCount', 1)))
            self.consume([row['moneyType']], [cost])
            self.shop_purchases[purchase_key] = self.shop_purchases.get(purchase_key, 0)+quantity
            spent = dict(self.activities.get('shop_spent', {}))
            spent[str(row['moneyType'])] = int(spent.get(str(row['moneyType']), 0))+cost
            self.activities['shop_spent'] = spent
            from daily_tasks import DailyTasks
            DailyTasks(self).record('purchase', quantity)

    def buy_pet(self, key):
        row = self.tables['PetShop'][str(key)]
        with self.transaction():
            self.consume([row['moneyType']], [int(row['price'])])
            pet = self.preset_pet(key, 'PetShop')
            self.receive_pet(pet)
        return pet

    def cure_cost(self):
        return None, 0  # PC edition: nurse care is permanently free.

    @atomic_mutation
    def cure_party(self):
        currency, amount = self.cure_cost()
        if currency:
            self.consume([currency], [amount])
        for pet in self.pets:
            pet.heal(self.tables)
        return currency, amount

    @atomic_mutation
    def submit_task(self, task_id, branch=False):
        task_id = int(task_id)
        completed = self.completed_branch if branch else self.completed_main
        if task_id in completed:
            return False
        if not branch and task_id != self.main_task:
            raise ValueError('Cannot submit a main task outside the current original sequence')
        row = self.tables['BranchTask' if branch else 'MainTask'][str(task_id)]
        rewards = []
        # A late invalid reward or failed random pet generation must roll back
        # the entire batch, not leave earlier rewards claimable again.
        self.grant_many(numbers(row['rewardIds']), numbers(row['rewardCounts']))
        for key, amount in zip(numbers(row['rewardIds']), numbers(row['rewardCounts'])):
            if amount:
                item = self.tables['Item'].get(str(key)) or self.tables['Pet'].get(str(key))
                rewards.append(f'{item.get("name", key) if item else key} × {amount}')
        self.last_rewards = rewards
        completed.append(task_id)
        if branch:
            self.branch_states[str(task_id)] = 5
            from task_progress import TaskProgress
            TaskProgress(self).update('branch_submit', task_id)
        else:
            next_task = int(row.get('nextTaskId', 0))
            self.main_task = next_task or task_id
            self.main_state = 3 if next_task else 5
            if next_task:
                from task_progress import TaskProgress
                TaskProgress(self).update()
        return True

    def add_preset(self, key):
        pet = self.preset_pet(key)
        self.receive_pet(pet)
        return pet

    @atomic_mutation
    def evolve(self, uid, *, use_gold=False):
        pet = next(p for p in self.pets+self.bank if p.uid == uid)
        if pet.trial_id:
            raise ValueError('试用宠物不能进化。')
        row = self.tables['Evolution'].get(pet.species)
        if not row or pet.level < int(row['level']):
            raise ValueError('未满足原版进化等级或该宠物不可进化')
        if use_gold:
            self.consume(['700001'], [EVOLUTION_GOLD_COST])
        else:
            self.consume(numbers(row['itemIds']), numbers(row['itemCounts']))
        pet.species = str(row['petId'])
        self.record_pet(pet.species)
        self.activities['evolve_total'] = int(self.activities.get('evolve_total', 0))+1
        stats = pet.stats(self.tables)
        pet.hp, pet.energy = min(pet.hp, stats[0]), min(pet.energy, stats[1])

    @atomic_mutation
    def merge_pets(self, base_uid, material_uids):
        """Original PetMerge: a bank base pet consumes same-quality materials.

        PetDataManager::petMerge (0x327218) adds attAddition to all ten
        variation/growth values, then recomputes quality/attributes.  The
        PlayerDataManager wrapper removes every material from bag or bank.
        Active party pets are not eligible ("当前参战宠物无法被融合").
        """
        material_uids = list(dict.fromkeys(material_uids))
        if base_uid in material_uids:
            raise ValueError('基础宠物不能同时作为融合材料。')
        base = next((p for p in self.bank if p.uid == base_uid), None)
        if base is None:
            raise ValueError('基础宠物必须在银行中，出战中不能融合。')
        materials = []
        for uid in material_uids:
            pet = next((p for p in self.bank if p.uid == uid), None)
            if pet is None:
                raise ValueError('融合材料必须是银行中的宠物。')
            materials.append(pet)
        recipe = next((row for row in self.tables['PetMerge'].values()
                       if int(row['petQuality']) == int(base.quality)), None)
        if recipe is None:
            raise ValueError('当前品质没有原版融合配方。')
        if len(materials) != int(recipe['petCount']):
            raise ValueError(f'需要 {recipe["petCount"]} 只同品质材料宠物。')
        for pet in materials:
            if int(pet.quality) != int(recipe['petQuality']) or pet.level < int(recipe['petLevel']):
                raise ValueError('材料宠物品质或等级不符合原版融合条件。')
        if self.count(recipe['moneyType']) < int(recipe['moneyCount']):
            raise ValueError('融合所需货币不足。')
        self.consume([recipe['moneyType']], [int(recipe['moneyCount'])])
        addition = float(recipe['attAddition'])
        base.variation = [add(value, addition) for value in base.variation]
        base.growth = [add(value, addition) for value in base.growth]
        for pet in materials:
            self.bank.remove(pet)
        base.update_quality(self.tables)
        stats = base.stats(self.tables)
        base.hp, base.energy = min(base.hp, stats[0]), min(base.energy, stats[1])
        return base

    @atomic_mutation
    def fuse_pets(self, uid_a, uid_b):
        """Original PetHeTi fusion (DataManager::createHeTiPet 0x31dd88).

        Both parents must be in the bank; active-party pets are rejected by the
        original UI.  The result is level 1, inherits the integer average of
        both parents' variation/growth, then uses the result pet's born-skill
        and talent probability tables.  Materials and both parents are removed
        in the same transaction.
        """
        if uid_a == uid_b:
            raise ValueError('选择两只不同的宠物。')
        a = next((p for p in self.bank if p.uid == uid_a), None)
        b = next((p for p in self.bank if p.uid == uid_b), None)
        if a is None or b is None:
            raise ValueError('只能合体银行中的宠物；出战宠物不能合体。')
        recipe = None
        for row in self.tables['PetHeTi'].values():
            # getHeTiData key = petA * 1000000 + petB; the recipe order is
            # significant (the UI has distinct left/right slots).
            if str(row['petAId']) == a.species and str(row['petBId']) == b.species:
                recipe = row
                break
        if recipe is None:
            raise ValueError('这两只宠物没有原版合体配方。')
        item_ids = numbers(recipe['costItemIds'])
        item_counts = numbers(recipe['costItemCounts'])
        if len(item_ids) != len(item_counts):
            raise ValueError('原版合体配方材料数量不一致。')
        for item, count in zip(item_ids, item_counts):
            if self.count(item) < count:
                raise ValueError('合体材料不足。')
        result_ids = numbers(recipe['petIds'])
        probabilities = numbers(recipe['pros'])
        if not result_ids:
            raise ValueError('原版合体配方没有结果宠物。')
        if len(result_ids) == 1:
            species = str(result_ids[0])
        else:
            from pet_factory import weighted_choice
            if len(probabilities) != len(result_ids):
                raise ValueError('原版合体概率数量不一致。')
            species = str(weighted_choice(self.rng, result_ids, probabilities))
        variation = [float(math.floor((a.variation[i]+b.variation[i])/2)) for i in range(5)]
        growth = [float(math.floor((a.growth[i]+b.growth[i])/2)) for i in range(5)]
        from pet_factory import generate_pet
        child = generate_pet(self.tables, self.rng, species, 1,
                             fixed_attributes=(variation, growth))
        child.exp = 0
        self.consume(item_ids, item_counts)
        self.bank.remove(a)
        self.bank.remove(b)
        self.bank.append(child)
        self.record_pet(child.species)
        return child

    @atomic_mutation
    def breakthrough_pet(self, uid):
        pet = next((p for p in self.pets+self.bank if p.uid == uid), None)
        if pet is None:
            raise ValueError('找不到这只宠物。')
        row = self.tables['PetTuPo'].get(str(pet.breakthrough+1))
        if row is None:
            raise ValueError('已达到原版突破上限。')
        self.consume([row['costMoneyType'], row['stuffId']],
                     [int(row['costMoneyCount']), int(row['stuffCount'])])
        pet.breakthrough += 1
        pet.heal(self.tables)
        return pet

    def payload(self):
        state = {key: copy.deepcopy(value) for key, value in self.__dict__.items()
                 if key not in ['tables', 'rng', 'pets', 'bank']}
        return {'format': self.FORMAT, 'state': state,
                'pets': [asdict(p) for p in self.pets], 'bank': [asdict(p) for p in self.bank],
                'random_state': self.rng.getstate()}

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix+'.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(self.payload(), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            backup = path.with_suffix(path.suffix+'.bak')
            import shutil
            shutil.copy2(path, backup)
        os.replace(temporary, path)

    @classmethod
    def load(cls, tables, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        if payload.get('format') != cls.FORMAT:
            raise ValueError('这是其他版本或仅保存位置的验证存档，不能当作完整游戏存档载入')
        result = cls(tables)
        fields = set(result.__dict__)-{'tables', 'rng', 'pets', 'bank'}
        if set(payload['state'])-fields:
            raise ValueError('Unrecognized save fields')
        for key, value in payload['state'].items():
            setattr(result, key, value)
        old_cash = int(result.inventory.pop('700003', 0))
        if old_cash:
            result.inventory['700001'] = result.inventory.get('700001', 0)+old_cash*GOLD_PER_FEN
        # 0.2.3 and older saves do not carry the arena rank/title fields.
        for field in ('arena_ranks', 'arena_titles', 'arena_wins', 'arena_streak'):
            if not hasattr(result, field):
                setattr(result, field, {})
        if not hasattr(result, 'infinite_level'):
            result.infinite_level = 1
        if not hasattr(result, 'infinite_highest'):
            result.infinite_highest = result.infinite_level
        if not hasattr(result, 'infinite_honor'):
            result.infinite_honor = 0
        init_row = tables['Init'][str(getattr(result, 'initialization', 1))]
        for arena_id in numbers(init_row.get('arenaIds', '')):
            key = str(arena_id)
            result.arena_ranks.setdefault(key, 101)
            result.arena_titles.setdefault(key, 0)
            result.arena_wins.setdefault(key, 0)
            result.arena_streak.setdefault(key, 0)
        result.inventory['700004'] = 6
        result.pets = [Pet(**p) for p in payload['pets']]
        result.bank = [Pet(**p) for p in payload['bank']]
        for key in tables['TrialPet']:
            if result.trial_pet_purchased(key):
                result.activities.setdefault('trial_purchased', {}).setdefault(key, 'legacy')
        # Older saves never tracked sightings. Recover owned species only;
        # constructor presets and unseen opponents must not become sightings.
        result.seen_species = list(dict.fromkeys(str(k) for k in payload['state'].get('seen_species', result.encyclopedia)))
        if any(k not in tables['Pet'] for k in result.seen_species):
            raise ValueError('存档的已见图鉴中存在未知宠物。')
        if 'starter_id' not in payload['state'] and result.sprite_id == '10001' and result.pets:
            result.starter_id = result.initialization
            result.initialization = 1
        def tuples(value):
            return tuple(tuples(x) for x in value) if isinstance(value, list) else value
        result.rng.setstate(tuples(payload['random_state']))
        if str(result.map_id) not in tables['VillageMap']:
            raise ValueError('存档中的原版地图不存在')
        for pet in result.pets+result.bank:
            if pet.species not in tables['Pet']:
                raise ValueError('存档中的宠物不存在')
        for species in list(result.encyclopedia):
            result.record_pet(species)
        return result
