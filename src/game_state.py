"""Persistent native game state, separate from the historical preview-position save."""
from __future__ import annotations

import copy
import json
import os
import random
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from game_formulas import attribute, level_exp, train_attribute, train_hp, train_mp


def numbers(value, cast=int):
    if isinstance(value, list):
        return [cast(v) for v in value]
    if not value or value == '0':
        return []
    return [cast(v) for v in str(value).split(',') if v.strip()]


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

    def __init__(self, tables, seed=None):
        self.tables = tables
        self.rng = random.Random(seed)
        self.map_id, self.x, self.y = 7401, 17*64+32, 0
        self.initialization = 2
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
        return pet

    def initialize(self, key):
        row = self.tables['Init'][str(key)]
        self.initialization = int(key)
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
        (self.pets if len(self.pets) < 6 else self.bank).append(pet)
        self.record_pet(pet.species)
        return pet

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

    def consume(self, ids, amounts):
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

    def use_item(self, item_id, pet=None):
        item_id = str(item_id)
        row = self.tables['Item'].get(item_id)
        if not row:
            raise ValueError('原版道具表中没有这个道具。')
        if int(row.get('useType', 0)) != 1:
            raise ValueError(f'{row.get("name", item_id)} 不是可在背包中使用的回复道具。')
        if self.count(item_id) <= 0:
            raise ValueError('道具数量不足。')
        if pet is None:
            pet = next((p for p in self.pets if p.hp < p.stats(self.tables)[0]), None)
        if pet is None:
            raise ValueError('当前没有需要回复的宠物。')
        description = str(row.get('des', ''))
        if '全回复' in description:
            pet.heal(self.tables)
        else:
            import re
            match = re.search(r'(\d+)', description)
            amount = int(match.group(1)) if match else 0
            if '生命' in description:
                pet.hp = min(pet.stats(self.tables)[0], pet.hp+amount)
            elif '能量' in description:
                pet.energy = min(pet.stats(self.tables)[1], pet.energy+amount)
            else:
                raise ValueError(f'{row.get("name", item_id)} 的回复字段尚未核定。')
        self.consume([item_id], [1])
        return f'{row.get("name", item_id)} 已用于 {self.tables["Pet"].get(str(pet.species), {}).get("name", pet.species)}。'

    def buy(self, table, key, quantity=1):
        if quantity <= 0:
            raise ValueError('Quantity must be positive')
        row = self.tables[table][str(key)]
        item_id = row['goodsKid']
        cost = int(row['price'])*quantity
        if self.count(row['moneyType']) < cost:
            raise ValueError('货币不足')
        if item_id in self.tables['Pet']:
            for _ in range(quantity):
                self.add_generated_pet(item_id)
        else:
            self.grant(item_id, quantity)
        self.consume([row['moneyType']], [cost])

    def submit_task(self, task_id, branch=False):
        task_id = int(task_id)
        completed = self.completed_branch if branch else self.completed_main
        if task_id in completed:
            return False
        if not branch and task_id != self.main_task:
            raise ValueError('Cannot submit a main task outside the current original sequence')
        row = self.tables['BranchTask' if branch else 'MainTask'][str(task_id)]
        self.last_rewards = []
        # Validate every reward BEFORE mutating, so a pending mechanic cannot partially grant it.
        for key, amount in zip(numbers(row['rewardIds']), numbers(row['rewardCounts'])):
            if str(key) in self.tables['Pet'] and amount < 0:
                raise ValueError('Negative pet reward')
        for key, amount in zip(numbers(row['rewardIds']), numbers(row['rewardCounts'])):
            self.grant(key, amount)
            if amount:
                item = self.tables['Item'].get(str(key)) or self.tables['Pet'].get(str(key))
                self.last_rewards.append(f'{item.get("name", key) if item else key} × {amount}')
        completed.append(task_id)
        if branch:
            self.branch_states[str(task_id)] = 5
        else:
            next_task = int(row.get('nextTaskId', 0))
            self.main_task = next_task or task_id
            self.main_state = 4 if next_task else 5
        return True

    def add_preset(self, key):
        pet = self.preset_pet(key)
        (self.pets if len(self.pets) < 6 else self.bank).append(pet)
        self.record_pet(pet.species)
        return pet

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
        def tuples(value):
            return tuple(tuples(x) for x in value) if isinstance(value, list) else value
        result.rng.setstate(tuples(payload['random_state']))
        if str(result.map_id) not in tables['VillageMap']:
            raise ValueError('存档中的原版地图不存在')
        for pet in result.pets+result.bank:
            if pet.species not in tables['Pet']:
                raise ValueError('存档中的宠物不存在')
        return result
