"""Persistent native game state, separate from the historical preview-position save."""
from __future__ import annotations

import copy
import json
import os
import random
import uuid
from contextlib import contextmanager
from functools import wraps
from dataclasses import asdict, dataclass, field
from pathlib import Path

from game_formulas import add, attribute, level_exp, train_attribute, train_hp, train_mp


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
        self.budokans = {}
        self.arenas = {}
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
        self.initialization = int(key)
        self.starter_id = 0
        self.player_name = '尼尔' if int(key) == 1 else '皮尔'
        self.sprite_id = row['spriteId']
        self.inventory = {str(k): n for k, n in zip(numbers(row['itemIds']), numbers(row['itemCounts']))}
        self.pets = [self.preset_pet(k) for k in numbers(row['petIds'])]
        for p in self.pets:
            self.record_pet(p.species)
        self.budokans = {str(k): value for k, value in zip(numbers(row['budokanIds']), numbers(row['budokanLevels']))}
        self.arenas = {str(k): value for k, value in zip(numbers(row['arenaIds']), numbers(row['arenaTitles']))}

    def record_pet(self, species):
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
        return self.inventory.get(str(item_id), 0)

    def grant(self, item_id, amount):
        item_id, amount = str(item_id), int(amount)
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
        self.inventory[item_id] = self.count(item_id)+amount

    def add_generated_pet(self, species, level=1):
        """Original random attributes, generated from the Pet probability columns."""
        from pet_factory import generate_pet
        pet = generate_pet(self.tables, self.rng, species, level)
        self.receive_pet(pet)
        return pet

    def pet_capacity(self, bank=False):
        key = '700005' if bank else '700004'
        return self.count(key) if key in self.inventory else (200 if bank else 6)

    def pet_free_slots(self):
        return max(0, self.pet_capacity()-len(self.pets))+max(0, self.pet_capacity(True)-len(self.bank))

    def receive_pet(self, pet):
        if len(self.pets) < self.pet_capacity():
            self.pets.append(pet)
        elif len(self.bank) < self.pet_capacity(True):
            self.bank.append(pet)
        else:
            raise ValueError('宠物背包和银行都已满。')
        self.record_pet(pet.species)

    def move_pet(self, uid, *, to_bank):
        source, destination = (self.pets, self.bank) if to_bank else (self.bank, self.pets)
        pet = next((p for p in source if p.uid == uid), None)
        if pet is None:
            raise ValueError('找不到这只宠物。')
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
        if not needs_recovery(pet):
            raise ValueError('这只宠物不需要此道具回复。')
        result = recovery(effect, pet.hp, pet.energy, *pet.stats(self.tables)[:2])
        pet.hp, pet.energy = result.hp, result.energy
        self.consume([item_id], [1])
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

    def buy_pet(self, key):
        row = self.tables['PetShop'][str(key)]
        with self.transaction():
            self.consume([row['moneyType']], [int(row['price'])])
            pet = self.preset_pet(key, 'PetShop')
            self.receive_pet(pet)
        return pet

    def cure_cost(self):
        if self.shop_purchases.get('Store:70201', 0):
            return None, 0
        return ('700006', 1) if self.count('700006') > 0 else ('700001', 100)

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
    def evolve(self, uid):
        pet = next(p for p in self.pets+self.bank if p.uid == uid)
        row = self.tables['Evolution'].get(pet.species)
        if not row or pet.level < int(row['level']):
            raise ValueError('未满足原版进化等级或该宠物不可进化')
        self.consume(numbers(row['itemIds']), numbers(row['itemCounts']))
        pet.species = str(row['petId'])
        self.record_pet(pet.species)
        stats = pet.stats(self.tables)
        pet.hp, pet.energy = min(pet.hp, stats[0]), min(pet.energy, stats[1])

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
        result.pets = [Pet(**p) for p in payload['pets']]
        result.bank = [Pet(**p) for p in payload['bank']]
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
