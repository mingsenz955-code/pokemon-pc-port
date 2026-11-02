"""Native turn-based battle engine built on the recovered 1.20.4 data.

What is taken directly from the original package:
  * every pet, skill, state, talent, enemy team, drop and capture-item row;
  * the standalone soft-float damage/experience/escape formulas that were
    compared against the ARM binary (see tools/check_original_formulas.py);
  * the capture chance skeleton disassembled in
    research/battle-stat-disassembly.txt (base rate + level/HP term + charm).
Runtime base damage now dispatches to the four recovered formula branches.
Full buff/talent damage revisions, special skills and state target selection
still require comparison with the original controller; see the evidence ledger.
"""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field

from game_formulas import (escape_rate, offer_exp, shared_exp, skill_damage,
                           attack_damage, defence_damage, speed_damage, energy_damage)
from game_state import numbers

# state key -> (display name, kind).  Keys are the original Skill.state values.
STATE_NAMES = {
    '1': ('魅惑', 'charm'), '2': ('中毒', 'poison'), '3': ('减防', 'def_down'),
    '4': ('减速', 'speed_down'), '5': ('睡眠', 'sleep'), '6': ('沉睡', 'sleep'),
    '7': ('石化', 'petrify'), '8': ('经验加成', 'exp_up'), '9': ('禁锢', 'bind'),
    '10': ('限制', 'restrict'), '11': ('力量增强', 'power_up'),
    '12': ('力量增强', 'power_up'), '13': ('生命流失', 'drain'),
    '14': ('背水一战', 'all_in'), '15': ('力量降低', 'power_down'),
    '16': ('生命削减', 'hp_cut'), '17': ('低血增伤', 'low_hp_boost'),
    '18': ('模仿', 'mimic'), '19': ('生命同等', 'equalize'),
    '20': ('生命为1', 'hp_one'), '21': ('吸收', 'absorb'),
    '22': ('反噬', 'recoil'), '23': ('治疗', 'heal'), '24': ('治疗', 'heal'),
    '25': ('治疗', 'heal'), '26': ('治疗', 'heal'), '27': ('治疗', 'heal'),
    '28': ('持续回复', 'regen'), '29': ('石化反击', 'counter'),
    '30': ('恐惧', 'fear'), '31': ('噩梦', 'nightmare'),
    '32': ('力量增强', 'power_up'), '33': ('防御增强', 'def_up'),
    '34': ('速度增强', 'speed_up'), '35': ('能量恢复', 'energy_heal'),
    '36': ('月饼', 'transform'), '38': ('一击致命', 'instant_kill'),
    '39': ('几率治疗', 'heal_chance'), '40': ('驱散', 'dispel'),
    '41': ('冰冻', 'freeze'), '42': ('力量大幅降低', 'power_down_big'),
    '43': ('力量大幅增强', 'power_up_45'), '44': ('防御大幅降低', 'def_down_big'),
    '45': ('力量伤害无效', 'immune_power'), '46': ('能量伤害无效', 'immune_energy'),
    '47': ('防御伤害无效', 'immune_def'), '48': ('速度伤害无效', 'immune_speed'),
    '49': ('寄生', 'leech'), '50': ('生命汲取', 'drain_hp'),
    '51': ('法力流失', 'energy_burn'), '52': ('死亡预言', 'doom'),
    '53': ('驱散异常', 'cleanse'), '54': ('速度大幅增强', 'speed_up_big'),
    '55': ('防御降低', 'def_down_35'), '56': ('力量降低', 'power_down_35'),
    '57': ('速度大幅降低', 'speed_down_big'),
}

SELF_STATES = {8, 11, 12, 14, 21, 22, 23, 24, 25, 26, 27, 28, 29, 33, 34, 35,
               36, 39, 43, 44, 45, 46, 47, 48, 53, 54, 55, 56, 57}
INSTANT_STATES = {16, 19, 20, 23, 24, 25, 26, 27, 35, 38, 39, 50, 51, 53}
DEBUFF_KINDS = {'poison', 'def_down', 'speed_down', 'sleep', 'sleep', 'petrify',
                'bind', 'restrict', 'drain', 'power_down', 'fear', 'nightmare',
                'power_down_big', 'def_down_big', 'power_down_35', 'speed_down_big'}
DOT_KINDS = {'poison', 'drain', 'leech', 'nightmare'}

# The original tables encode skill coefficients as decimal strings.
ATTRIBUTE_INDEX = {'0': 2, '1': 4, '2': 3, '3': 1}


def _pairs(raw):
    values = [int(float(v)) for v in str(raw or '').split(',') if v.strip() != '']
    return list(zip(values[::2], values[1::2]))


@dataclass
class Buff:
    key: str
    rounds: int
    parameter: str
    buff_type: int
    source: str = ''
    name: str = ''

    @property
    def values(self):
        return [int(float(v)) for v in self.parameter.split(':')[0].split(',') if v.strip()]

    @property
    def kind(self):
        return STATE_NAMES.get(self.key, ('未知状态', 'unknown'))[1]


class BattlePet:
    """A party member inside a battle.  Wraps the persistent Pet object."""

    def __init__(self, pet, side, slot, tables):
        self.pet = pet
        self.side = side
        self.slot = slot
        self.tables = tables
        self.stats = pet.stats(tables)
        self.base_stats = list(self.stats)
        self.max_hp = max(1, self.stats[0])
        self.max_energy = max(1, self.stats[1])
        self.hp = pet.hp if pet.hp >= 0 else self.max_hp
        self.energy = pet.energy if pet.energy >= 0 else self.max_energy
        self.hp = max(0, min(self.hp, self.max_hp))
        self.energy = max(0, min(self.energy, self.max_energy))
        self.buffs: list[Buff] = []
        self.cooldowns = {}
        self.last_skill = ''
        self.participated = False
        self.transformed = None
        self._apply_talent_stats()

    # -- original talent passives -------------------------------------------
    def _apply_talent_stats(self):
        row = self.tables['Pet'][self.pet.species]
        boost = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        for key in self.pet.talents:
            talent = self.tables['Talent'].get(str(key))
            if not talent:
                continue
            for part in talent['state'].split(':'):
                values = [float(v) for v in part.split(',') if v.strip()]
                if len(values) < 3:
                    continue
                state, mode, value = int(values[0]), int(values[1]), values[2]
                if mode != 9:
                    continue
                if state == 24:
                    boost[0] += value
                elif state == 25:
                    boost[2] += value
                elif state == 26:
                    boost[4] += value
                elif state == 27:
                    self.energy_cost_reduction = min(100.0, value)
                elif state == 28:
                    self.crit_bonus = value
        self.talent_boost = boost
        for index, pct in boost.items():
            if pct:
                self.stats[index] = int(self.stats[index]*(1+pct/100))
        self.max_hp = max(1, self.stats[0])

    # -- stats ---------------------------------------------------------------
    def effective(self, index):
        pct = 0.0
        for buff in self.buffs:
            kind = buff.kind
            if kind in ('power_up', 'power_up_45') and index == 2:
                pct += 25 if kind == 'power_up' else 45
            elif kind == 'power_down' and index == 2:
                pct -= 25
            elif kind in ('power_down_big',) and index == 2:
                pct -= 80
            elif kind in ('power_down_35',) and index == 2:
                pct -= 35
            elif kind == 'def_up' and index == 3:
                pct += 25
            elif kind in ('def_down', 'def_down_35', 'def_down_big') and index == 3:
                pct -= 25 if kind == 'def_down' else 35
            elif kind == 'speed_up' and index == 4:
                pct += 40
            elif kind == 'speed_up_big' and index == 4:
                pct += 70
            elif kind == 'speed_down' and index == 4:
                pct -= 40
            elif kind in ('bind',) and index == 4:
                pct -= 40
            elif kind == 'speed_down_big' and index == 4:
                pct -= 60
        return max(1, int(self.stats[index]*(1+pct/100)))

    @property
    def alive(self):
        return self.hp > 0

    @property
    def name(self):
        return self.tables['Pet'][self.pet.species]['name']

    def has(self, *kinds):
        return any(buff.kind in kinds for buff in self.buffs)

    def has_state(self, key):
        return any(buff.key == str(key) for buff in self.buffs)

    def add_buff(self, key, buff):
        old = next((b for b in self.buffs if b.key == key), None)
        if old:
            self.buffs.remove(old)
        self.buffs.append(buff)

    def remove_buffs(self, *, beneficial=None, debuff=None):
        removed = []
        for buff in list(self.buffs):
            bad = buff.kind in DEBUFF_KINDS
            if beneficial is True and bad:
                continue
            if debuff is True and not bad:
                continue
            self.buffs.remove(buff)
            removed.append(buff)
        return removed

    def take_damage(self, amount, source=None, attribute=None):
        amount = max(0, int(amount))
        if amount <= 0:
            return 0
        absorb = next((buff for buff in self.buffs if buff.kind == 'absorb'), None)
        if absorb:
            self.buffs.remove(absorb)
            self.add_buff('5', Buff('5', 4, '14,5', 2, name='睡眠'))
            return 0
        for buff in list(self.buffs):
            if buff.kind.startswith('immune_') and attribute is not None:
                if buff.kind == f'immune_{attribute}':
                    return 0
        if self.has('counter') and source is not None:
            source.take_damage(max(1, amount//2))
        self.hp = max(0, self.hp-amount)
        return amount

    def heal(self, amount):
        amount = max(0, int(amount))
        before = self.hp
        self.hp = min(self.max_hp, self.hp+amount)
        return self.hp-before

    def restore_energy(self, amount):
        before = self.energy
        self.energy = min(self.max_energy, self.energy+max(0, int(amount)))
        return self.energy-before

    def cost(self, skill):
        base = int(skill['energyCost'])
        reduction = getattr(self, 'energy_cost_reduction', 0.0)
        if self.has('restrict'):
            return 10**9
        return max(0, int(base*(1-reduction/100)))

    def snapshot(self):
        return {'species': self.pet.species, 'level': self.pet.level,
                'hp': self.hp, 'energy': self.energy,
                'buffs': [b.__dict__ for b in self.buffs],
                'cooldowns': dict(self.cooldowns), 'last_skill': self.last_skill,
                'participated': self.participated}


class Battle:
    def __init__(self, tables, player_pets, enemy_specs, rng, *,
                 kind='trainer', name='', fight_row=None, bgm='0',
                 can_catch=False, can_escape=False, catch_items=None):
        self.tables = tables
        self.rng = rng
        self.kind = kind
        self.name = name
        self.fight_row = fight_row or {}
        self.enemy_items = {}
        for item, count in zip(numbers(self.fight_row.get('itemIds', '0')),
                               numbers(self.fight_row.get('itemCounts', '0'))):
            if item and count > 0:
                self.enemy_items[str(item)] = self.enemy_items.get(str(item), 0)+count
        self.bgm = bgm
        self.can_catch = can_catch
        self.can_escape = can_escape
        self.catch_items = catch_items or ['220004', '220005', '220006']
        self.player = [BattlePet(pet, 'player', i, tables) for i, pet in enumerate(player_pets)]
        self.enemy = []
        for i, spec in enumerate(enemy_specs):
            if hasattr(spec, 'stats'):
                pet = spec
            else:
                pet = self._make_enemy_pet(spec)
            self.enemy.append(BattlePet(pet, 'enemy', i, tables))
        self.player_index = 0
        self.enemy_index = 0
        self.round = 0
        self.result = None
        self.messages = []
        self.events = []
        self.force_switch = False
        self.last_catch_chance = 0
        self.caught_pet = None
        self.exp_gained = []
        self.drops = []
        self.damage_dealt = 0
        self.rewards_applied = False
        self._start_messages()
        self._check_end()

    def _make_enemy_pet(self, spec):
        from pet_factory import generate_pet
        if spec.get('pet'):
            return spec['pet']
        species = str(spec['species'])
        pet = generate_pet(self.tables, self.rng, species, spec.get('level', 1))
        # Enemy rows carry explicit growth/variation and skill sets; they take
        # precedence over generated values, exactly as the NpcPet table does.
        if spec.get('variation'):
            pet.variation = [float(v) for v in spec['variation']]
        if spec.get('growth'):
            pet.growth = [float(v) for v in spec['growth']]
        if spec.get('skills'):
            pet.skills = [str(v) for v in spec['skills']][:4]
        if spec.get('talents'):
            pet.talents = [str(v) for v in spec['talents']]
        if spec.get('held_item'):
            pet.held_item = str(spec['held_item'])
        pet.heal(self.tables)
        return pet

    def _start_messages(self):
        active = self.player_active
        enemy = self.enemy_active
        if active and enemy:
            self.messages.append(f'{enemy.name} Lv.{enemy.pet.level} 出现了！')
            self.messages.append(f'去吧，{active.name}！')

    def select_initial_player(self, index):
        """Use the party's selected lead without reordering its persistent slots."""
        if self.round or self.events:
            raise ValueError('Cannot change the opening pet after battle starts')
        if not (0 <= index < len(self.player) and self.player[index].alive):
            index = next((i for i, unit in enumerate(self.player) if unit.alive), 0)
        self.player_index = index
        self.force_switch = False
        self.messages = []
        self._start_messages()
        self._check_end()

    # -- team helpers --------------------------------------------------------
    @property
    def player_active(self):
        return self.player[self.player_index] if self.player_index < len(self.player) else None

    @property
    def enemy_active(self):
        return self.enemy[self.enemy_index] if self.enemy_index < len(self.enemy) else None

    def _next_alive(self, team, current):
        for offset in range(1, len(team)+1):
            index = (current+offset) % len(team)
            if team[index].alive:
                return index
        return None

    def _sync_pet(self, unit):
        unit.pet.hp = unit.hp
        unit.pet.energy = unit.energy

    def available_skills(self, unit):
        result = []
        for skill_id in unit.pet.skills:
            row = self.tables['Skill'].get(str(skill_id))
            if not row:
                continue
            cooldown = unit.cooldowns.get(str(skill_id), 0)
            result.append({'id': str(skill_id), 'row': row,
                           'usable': unit.energy >= unit.cost(row) and cooldown <= 0,
                           'cooldown': cooldown})
        return result

    # -- player actions ------------------------------------------------------
    def choose_skill(self, index):
        """index 0 is the original normal attack, 1..4 are the four skills."""
        if self.result or self.force_switch:
            return []
        if type(index) is not int or index < 0:
            return []
        unit = self.player_active
        if index == 0:
            action = {'type': 'attack'}
        else:
            skills = self.available_skills(unit)
            if index-1 >= len(skills):
                return []
            entry = skills[index-1]
            if not entry['usable']:
                self.messages.append('能量不足或技能仍在冷却中。')
                return []
            action = {'type': 'skill', 'id': entry['id'], 'row': entry['row']}
        return self._perform_round(action)

    def choose_item(self, item_id):
        if self.result or self.force_switch:
            return []
        item_id = str(item_id)
        if item_id not in self.catch_items:
            row = self.tables['Item'].get(item_id)
            if not row or int(row.get('useType', 0)) not in (1, 3):
                self.messages.append('该道具不能在战斗中使用。')
                return []
        unit = self.player_active
        if unit.has('restrict'):
            self.messages.append(f'{unit.name} 处于限制状态，无法使用道具。')
            return []
        if item_id in self.catch_items:
            if not self.can_catch:
                self.messages.append('训练师对战中不能捕捉对方的宠物。')
                return []
            return self._attempt_catch(item_id)
        return self._perform_round({'type': 'item', 'id': item_id})

    def choose_switch(self, index):
        if self.result:
            return []
        unit = self.player[index] if 0 <= index < len(self.player) else None
        if not unit or not unit.alive:
            self.messages.append('这只宠物已经无法战斗。')
            return []
        if self.force_switch:
            self.player_index = index
            self.force_switch = False
            self.messages.append(f'换上 {unit.name}！')
            return []
        if index == self.player_index:
            return []
        if self.player_active.has('charm', 'bind'):
            self.messages.append(f'{self.player_active.name} 处于魅惑/禁锢状态，无法替换。')
            return []
        return self._perform_round({'type': 'switch', 'index': index})

    def choose_escape(self):
        if self.result or self.force_switch:
            return []
        if not self.can_escape:
            self.messages.append('训练师对战中不能逃跑。')
            return []
        unit = self.player_active
        if unit.has('charm', 'bind', 'restrict'):
            self.messages.append('当前状态无法逃跑。')
            return []
        enemy = self.enemy_active
        rate = escape_rate(unit.effective(4), enemy.effective(4))
        if self.rng.randrange(100) < rate:
            self.messages.append('成功逃走了！')
            self.result = 'escape'
            self.events.append({'type': 'escape', 'rate': rate})
            self._finish()
        else:
            self.messages.append('没能逃走！')
            self.events.append({'type': 'escape_failed', 'rate': rate})
            self._perform_round({'type': 'escape_failed'})
        return list(self.events)

    # -- round execution -----------------------------------------------------
    def _perform_round(self, player_action):
        self.events = []
        self.round += 1
        self.messages = []
        player = self.player_active
        enemy = self.enemy_active
        if not player or not enemy:
            self._check_end()
            return list(self.events)
        player.participated = True

        # Skip states are consumed before choosing an action.
        if self._skip_turn(player):
            player_action = {'type': 'skip'}
        enemy_action = self._enemy_action()
        if self._skip_turn(enemy):
            enemy_action = {'type': 'skip'}

        order = self._action_order(player, enemy, player_action, enemy_action)
        for side in order:
            if self.result:
                break
            # A switch changes the opponent's target during this same round.
            unit, target = ((self.player_active, self.enemy_active) if side == 'player'
                            else (self.enemy_active, self.player_active))
            action = player_action if side == 'player' else enemy_action
            if not unit.alive or not target.alive:
                continue
            self._execute(unit, target, action, side)

        if not self.result:
            self._end_round()
            self._check_end()
        if self.force_switch and not self.result:
            self.messages.append(f'{self.player_active.name} 已失去战斗能力，请更换宠物。')
        for unit in self.player+self.enemy:
            self._sync_pet(unit)
        return list(self.events)

    def _action_order(self, player, enemy, player_action, enemy_action):
        priority = {'switch': 3, 'item': 2, 'catch': 2, 'escape': 2,
                    'skill': 1, 'attack': 1, 'skip': 0, 'escape_failed': 0}
        pp = priority.get(player_action['type'], 1)
        pe = priority.get(enemy_action['type'], 1)
        if pp != pe:
            return ['player', 'enemy'] if pp > pe else ['enemy', 'player']
        if player_action['type'] in ('attack', 'skill'):
            ps, es = player.effective(4), enemy.effective(4)
            if ps != es:
                return ['player', 'enemy'] if ps > es else ['enemy', 'player']
            return ['player', 'enemy'] if self.rng.random() < .5 else ['enemy', 'player']
        return ['player', 'enemy']

    def _skip_turn(self, unit):
        if unit.has('sleep', 'petrify', 'freeze'):
            self.messages.append(f'{unit.name} 无法行动！')
            self.events.append({'type': 'skip', 'side': unit.side, 'name': unit.name})
            return True
        if unit.has('fear') and self.rng.random() < .5:
            self.messages.append(f'{unit.name} 被恐惧，无法行动！')
            self.events.append({'type': 'skip', 'side': unit.side, 'name': unit.name})
            return True
        return False

    def _enemy_action(self):
        unit = self.enemy_active
        if unit.hp/unit.max_hp*100 <= self._enemy_heal_threshold():
            item = self._enemy_heal_item()
            if item and self.rng.randrange(100) < self._enemy_heal_rate():
                return {'type': 'item', 'id': item}
        options = [entry for entry in self.available_skills(unit) if entry['usable']]
        if options and self.rng.random() < .85:
            entry = self.rng.choice(options)
            return {'type': 'skill', 'id': entry['id'], 'row': entry['row']}
        return {'type': 'attack'}

    def _enemy_heal_threshold(self):
        values = numbers(self.fight_row.get('targetHp', '0'))
        return max(values) if values else 0

    def _enemy_heal_rate(self):
        values = numbers(self.fight_row.get('useItemRate', '0'))
        return values[0] if values else 0

    def _enemy_heal_item(self):
        for item, count in self.enemy_items.items():
            if count > 0 and item in self.tables['Item']:
                return item
        return None

    def _use_item(self, unit, target, item_id):
        from item_effects import recovery
        row = self.tables['Item'].get(str(item_id), {})
        effect = self.tables.get('PetItem', {}).get(str(item_id))
        if effect is None:
            self.messages.append('该道具的原版效果尚未接入。')
            return False
        try:
            result = recovery(effect, target.hp, target.energy, target.max_hp, target.max_energy)
        except ValueError as error:
            self.messages.append(str(error))
            return False
        changed = (target.hp, target.energy) != (result.hp, result.energy)
        if result.cleanse:
            changed = bool(target.remove_buffs(debuff=True)) or changed
        if not changed:
            self.messages.append('这只宠物不需要此道具。')
            return False
        target.hp, target.energy = result.hp, result.energy
        self._sync_pet(target)
        self.messages.append(f'{unit.name} 使用了 {row.get("name", item_id)}！')
        self.events.append({'type': 'item_used', 'side': unit.side, 'id': str(item_id)})
        return True

    def _execute(self, unit, target, action, side):
        kind = action['type']
        if kind == 'skip':
            return
        if kind == 'switch':
            self._switch(unit, action['index'])
            return
        if kind == 'item':
            item_id = action['id']
            if side == 'enemy':
                if self.enemy_items.get(str(item_id), 0) > 0 and self._use_item(unit, unit, item_id):
                    self.enemy_items[str(item_id)] -= 1
            else:
                self._use_item(unit, unit, item_id)
            return
        if kind == 'escape_failed':
            return
        if kind == 'attack':
            self._attack(unit, target)
            return
        if kind == 'skill':
            self._use_skill(unit, target, action['row'])

    def _switch(self, unit, index):
        team = self.player if unit.side == 'player' else self.enemy
        new = team[index]
        if unit.side == 'player':
            self.player_index = index
        else:
            self.enemy_index = index
        self.messages.append(f'换上 {new.name}！')
        self.events.append({'type': 'switch', 'side': unit.side, 'name': new.name})

    def _attack(self, unit, target):
        self.messages.append(f'{unit.name} 的普通攻击！')
        self.events.append({'type': 'attack', 'side': unit.side, 'name': unit.name, 'uid': unit.pet.uid})
        row = self.tables.get('Skill', {}).get('300056', {'attack': 0, 'attackCoe': 1})
        self._deal(unit, target, self._base_damage(unit, target, 'power'), 'power',
                   crit_chance=self._crit_chance(unit, target, row), skill=row)

    def _use_skill(self, unit, target, skill):
        cost = unit.cost(skill)
        if unit.energy < cost:
            self._attack(unit, target)
            return
        unit.energy -= cost
        cooldown = int(skill.get('coolDown', 0))
        if cooldown:
            unit.cooldowns[str(skill['keyId'])] = cooldown
        unit.last_skill = str(skill['keyId'])
        self.messages.append(f'{unit.name} 使用了 {skill["name"]}！')
        self.events.append({'type': 'skill', 'side': unit.side, 'name': unit.name,
                            'uid': unit.pet.uid,
                            'skill': skill['name'], 'skill_id': skill['keyId']})
        attack_count = max(1, int(skill.get('attackCount', 1) or 1))
        coe = float(skill.get('attackCoe', 0) or 0)
        hit = False
        for _ in range(attack_count):
            if attack_count > 1:
                rate = int(skill.get('attackRate', 100) or 100)
                if rate < 100 and self.rng.randrange(100) >= rate:
                    continue
            if coe > 0:
                attr = ATTRIBUTE_INDEX.get(str(skill.get('mainAttribute', '0')), 2)
                attribute = {'2': 'power', '3': 'defence', '4': 'speed', '1': 'energy'}[str(attr)]
                damage = self._base_damage(unit, target, attribute)
                # 300052: doubles when the opponent is below half HP.
                if '17' in str(skill.get('state', '')) + str(skill.get('state2', '')) and target.hp/target.max_hp < .5:
                    damage *= 2
                if unit.has('all_in') and unit.has('poison', 'drain'):
                    damage *= 2
                self._deal(unit, target, damage, attribute,
                           crit_chance=self._crit_chance(unit, target, skill), skill=skill)
                hit = True
        self._apply_states(unit, target, skill)
        if not hit and coe <= 0:
            self.events.append({'type': 'status', 'skill': skill['name']})

    def _crit_chance(self, unit, target, skill):
        base = 15
        cri = self.tables['Cri'].get(str(self.tables['Pet'][unit.pet.species].get('restraint', '3')))
        if cri:
            try:
                base = int(cri['self'])
                mutual = numbers(cri['mutual'])
                target_attr = int(self.tables['Pet'][target.pet.species].get('restraint', '0') or 0)
                if 0 < target_attr <= len(mutual):
                    base += mutual[target_attr-1]
            except (KeyError, ValueError):
                pass
        base += getattr(unit, 'crit_bonus', 0)
        base += int(float(skill.get('critRevise', 0) or 0))
        return max(0, min(100, base))

    def _deal(self, unit, target, damage, attribute, crit=False, crit_chance=None, skill=None):
        crit = crit if crit_chance is None else self.rng.randrange(100) < crit_chance
        # damageAddition 0x2c91bc adds 50 to the restraint percentage on a
        # critical hit, BEFORE Formula_PetSkillAttackDamage. No +/-5% jitter.
        percent = 100
        attacker_restraint = str(self.tables['Pet'][unit.pet.species].get('restraint', '0'))
        defender_restraint = int(self.tables['Pet'][target.pet.species].get('restraint', '0') or 0)
        contrast = self.tables['Contrast'].get(attacker_restraint)
        if contrast and 0 < defender_restraint <= len(numbers(contrast['mutual'])):
            percent = numbers(contrast['mutual'])[defender_restraint-1]
        damage = int(damage*(percent+(50 if crit else 0))/100)
        if skill is not None:
            damage = skill_damage(damage, int(skill.get('attack', 0) or 0),
                                  round(float(skill.get('attackCoe', 0) or 0)*100))
        damage = self._reduce_talent_damage(damage, target)
        if unit.has('leech') and damage > 0:
            for buff in unit.buffs:
                if buff.kind == 'leech':
                    source = unit
                    source.heal(max(1, int(damage*.1)))
        was_alive = target.alive
        taken = target.take_damage(damage, source=unit, attribute=attribute)
        if unit.side == 'player' and target.side == 'enemy':
            self.damage_dealt += taken
        self.events.append({'type': 'damage', 'side': target.side, 'name': target.name,
                            'uid': target.pet.uid,
                            'amount': taken, 'crit': crit, 'attribute': attribute,
                            'hp': target.hp, 'max_hp': target.max_hp})
        if taken == 0:
            self.messages.append(f'{target.name} 没有受到伤害。')
        else:
            self.messages.append(f'{target.name} 受到 {taken} 点伤害' + ('（暴击）' if crit else '') + '。')
        if unit.has('recoil') and damage > 0:
            recoil = max(1, int(damage*0.15))
            unit.take_damage(recoil)
            self.messages.append(f'{unit.name} 受到 {recoil} 点反噬伤害。')
        if not target.alive:
            self.messages.append(f'{target.name} 倒下了！')
            self.events.append({'type': 'faint', 'side': target.side, 'name': target.name})
            if was_alive and unit.side == 'player':
                self.events.append({'type': 'oneshot', 'side': 'player', 'name': target.name})

    def _base_damage(self, unit, target, attribute):
        # checkPetUseSkill 0x2c84d2..0x2c85d0; default damage revisions are
        # zero. Buff/talent damage revisions still require a separate audit.
        if attribute == 'power':
            return attack_damage(unit.effective(2), target.effective(3), 0, 0)
        if attribute == 'speed':
            return speed_damage(unit.effective(4), target.effective(4), target.effective(3), 0, 0)
        if attribute == 'defence':
            return defence_damage(unit.effective(3), target.max_energy, target.effective(3), 0, 0)
        if attribute == 'energy':
            return energy_damage(unit.max_energy, target.max_energy, 0, 0)
        raise ValueError(f'Unknown original damage attribute {attribute}')

    def _reduce_talent_damage(self, damage, target):
        for key in target.pet.talents:
            talent = self.tables['Talent'].get(str(key))
            if not talent:
                continue
            for part in talent['state'].split(':'):
                values = [float(v) for v in part.split(',') if v.strip()]
                if len(values) >= 3 and int(values[1]) == 3 and int(values[0]) == 43:
                    damage = int(damage*(1-values[2]/100))
        return max(1, int(damage))

    # -- states --------------------------------------------------------------
    def _apply_states(self, unit, target, skill):
        for field_name in ('state', 'state2'):
            for index, chance in _pairs(skill.get(field_name, '')):
                if index == 0:
                    continue
                receiver = unit if int(index) in SELF_STATES else target
                if not receiver.alive:
                    continue
                roll = self.rng.randrange(100)
                if roll >= chance:
                    continue
                key = str(index)
                state = self.tables['SkillState'].get(key)
                if not state:
                    self.events.append({'type': 'unknown_state', 'key': key})
                    continue
                if self._immune(receiver, key):
                    self.messages.append(f'{receiver.name} 免疫了{STATE_NAMES.get(key, ("状态",))[0]}！')
                    continue
                self._apply_state(unit, receiver, key, state)
                if receiver.side != unit.side and key in ('5', '6', '7'):
                    self.events.append({'type': 'state_applied', 'kind': STATE_NAMES[key][1],
                                        'name': receiver.name})

    def _immune(self, unit, key):
        for talent_id in unit.pet.talents:
            talent = self.tables['Talent'].get(str(talent_id))
            if not talent:
                continue
            for part in talent['state'].split(':'):
                values = [int(float(v)) for v in part.split(',') if v.strip()]
                if len(values) >= 3 and int(values[1]) == 1 and values[0] == int(key) and values[2] >= 100:
                    return True
        return False

    def _apply_state(self, unit, receiver, key, state):
        name, kind = STATE_NAMES.get(key, ('未知状态', 'unknown'))
        values = [int(float(v)) for v in state['parameter'].split(':')[0].split(',') if v.strip()]
        rounds = max(1, int(state['round']))
        if kind in ('heal', 'heal_chance'):
            pct = values[1] if len(values) > 1 else 15
            healed = receiver.heal(receiver.max_hp*pct//100)
            self.messages.append(f'{receiver.name} 回复了 {healed} 点生命。')
            self.events.append({'type': 'heal', 'side': receiver.side, 'amount': healed})
            if kind == 'heal_chance' and self.rng.randrange(100) < 30:
                healed = receiver.heal(receiver.max_hp)
                self.messages.append(f'{receiver.name} 回复了全部生命！')
        elif kind == 'energy_heal':
            pct = values[1] if len(values) > 1 else 30
            amount = receiver.restore_energy(receiver.max_energy*pct//100)
            self.messages.append(f'{receiver.name} 回复了 {amount} 点能量。')
        elif kind == 'hp_cut':
            receiver.hp = max(1, receiver.hp-receiver.max_hp//4)
            self.messages.append(f'{receiver.name} 的生命被削减了四分之一！')
        elif kind == 'equalize':
            receiver.hp = max(1, min(receiver.hp, unit.hp))
            self.messages.append(f'{receiver.name} 的生命值与对手相同了！')
        elif kind == 'hp_one':
            receiver.hp = 1
            self.messages.append(f'{receiver.name} 的生命值降为 1！')
        elif kind == 'instant_kill':
            receiver.hp = 0
            self.messages.append(f'{receiver.name} 被一击致命！')
        elif kind == 'drain_hp':
            pct = values[1] if len(values) > 1 else 20
            amount = max(1, receiver.max_hp*pct//100)
            receiver.take_damage(amount, source=unit)
            unit.heal(amount)
            self.messages.append(f'{unit.name} 汲取了 {receiver.name} 的 {amount} 点生命！')
        elif kind == 'energy_burn':
            pct = values[1] if len(values) > 1 else 80
            receiver.energy = max(0, receiver.energy-receiver.max_energy*pct//100)
            self.messages.append(f'{receiver.name} 的能量被削减了！')
        elif kind == 'cleanse':
            receiver.remove_buffs(debuff=True)
            self.messages.append(f'{receiver.name} 的异常状态被驱散了！')
        elif kind == 'dispel':
            receiver.remove_buffs(beneficial=True)
            self.messages.append(f'{receiver.name} 的有益状态被驱散了！')
        else:
            receiver.add_buff(key, Buff(key, rounds, state['parameter'],
                                        int(state['buffType']), unit.pet.uid, name))
            self.messages.append(f'{receiver.name} 进入了{name}状态！')
            self.events.append({'type': 'buff', 'side': receiver.side, 'name': name,
                                'rounds': rounds, 'key': key})

    # -- end of round --------------------------------------------------------
    def _end_round(self):
        for unit in self.player+self.enemy:
            if not unit.alive:
                continue
            for buff in list(unit.buffs):
                kind = buff.kind
                values = buff.values
                if kind == 'poison':
                    pct = values[1] if len(values) > 1 else 15
                    amount = max(1, unit.max_hp*pct//100)
                    unit.take_damage(amount)
                    self.messages.append(f'{unit.name} 受到中毒伤害 {amount}。')
                elif kind == 'drain':
                    pct = values[1] if len(values) > 1 else 10
                    amount = max(1, unit.max_hp*pct//100)
                    unit.take_damage(amount)
                    self.messages.append(f'{unit.name} 受到生命流失 {amount}。')
                elif kind == 'leech':
                    pct = values[1] if len(values) > 1 else 10
                    amount = max(1, unit.max_hp*pct//100)
                    unit.take_damage(amount)
                    source = next((p for p in self.enemy+self.player if p.pet.uid == buff.source), None)
                    if source and source.alive:
                        source.heal(amount)
                    self.messages.append(f'{unit.name} 被汲取了 {amount} 点生命。')
                elif kind == 'regen':
                    pct = values[1] if len(values) > 1 else 15
                    healed = unit.heal(unit.max_hp*pct//100)
                    self.messages.append(f'{unit.name} 回复了 {healed} 点生命。')
                elif kind == 'nightmare':
                    amount = max(1, unit.max_hp*15//100)
                    unit.take_damage(amount)
                    unit.energy = max(0, unit.energy-unit.max_energy*15//100)
                elif kind == 'doom':
                    if buff.rounds <= 1:
                        unit.hp = 1
                        self.messages.append(f'{unit.name} 的死亡预言应验了，生命降为 1！')
                buff.rounds -= 1
                if buff.rounds <= 0:
                    unit.buffs.remove(buff)
            for skill_id in list(unit.cooldowns):
                unit.cooldowns[skill_id] -= 1
                if unit.cooldowns[skill_id] <= 0:
                    del unit.cooldowns[skill_id]
            if not unit.alive:
                self.messages.append(f'{unit.name} 倒下了！')
                self.events.append({'type': 'faint', 'side': unit.side, 'name': unit.name})

    def _check_end(self):
        if self.result:
            return
        if not any(unit.alive for unit in self.enemy):
            self.result = 'win'
            self._finish()
            return
        if not any(unit.alive for unit in self.player):
            self.result = 'lose'
            self._finish()
            return
        if not self.enemy_active or not self.enemy_active.alive:
            index = self._next_alive(self.enemy, self.enemy_index)
            if index is not None:
                self.enemy_index = index
                self.messages.append(f'对手换上了 {self.enemy_active.name}！')
                self.events.append({'type': 'enemy_switch', 'name': self.enemy_active.name})
        if not self.player_active or not self.player_active.alive:
            index = self._next_alive(self.player, self.player_index)
            if index is not None:
                self.force_switch = True

    def _finish(self):
        for unit in self.player+self.enemy:
            self._sync_pet(unit)
        if self.result == 'win':
            self._award()

    # -- capture -------------------------------------------------------------
    def capture_chance(self, item_id):
        enemy = self.enemy_active
        if not enemy:
            return 0
        function = self.tables['FunctionItem'].get(str(item_id))
        base = numbers(function['parameters'])[0] if function else 0
        hp_pct = enemy.hp/enemy.max_hp if enemy.max_hp else 0
        chance = base + 67 - int(65*hp_pct*hp_pct)
        if enemy.has_state('1'):
            chance += 20
        return max(1, min(100, chance))

    def _attempt_catch(self, item_id):
        self.events = []
        self.round += 1
        item = self.tables['Item'].get(str(item_id), {})
        self.messages = [f'投出了 {item.get("name", "精灵球")}！']
        self.last_catch_chance = self.capture_chance(item_id)
        roll = self.rng.randrange(100)+1
        self.events.append({'type': 'catch_attempt', 'chance': self.last_catch_chance})
        if roll <= self.last_catch_chance:
            self.messages.append(f'捕捉成功！({roll} <= {self.last_catch_chance})')
            target = self.enemy_active
            caught = copy.deepcopy(target.pet)
            caught.hp = max(1, target.hp)
            caught.energy = target.energy
            self.caught_pet = caught
            self.result = 'caught'
            self.events.append({'type': 'caught', 'name': caught.species,
                                'chance': self.last_catch_chance})
            self._finish()
        else:
            self.messages.append(f'从球里逃出来了！({roll} > {self.last_catch_chance})')
            self.events.append({'type': 'catch_failed', 'chance': self.last_catch_chance})
            enemy_action = self._enemy_action()
            self._execute(self.enemy_active, self.player_active, enemy_action, 'enemy')
            self._end_round()
            self._check_end()
        for unit in self.player+self.enemy:
            self._sync_pet(unit)
        return list(self.events)

    # -- rewards -------------------------------------------------------------
    def _award(self):
        level = max((unit.pet.level for unit in self.enemy), default=1)
        alive = [unit for unit in self.player if unit.alive and unit.participated]
        if not alive:
            return
        total = shared_exp(level, 1.0, 0, len(alive))
        for unit in alive:
            before = unit.pet.level
            gained = total
            levels = unit.pet.add_exp(gained, self.tables)
            self.exp_gained.append((unit.name, gained, levels))
            self.messages.append(f'{unit.name} 获得 {gained} 点经验。')
            if levels:
                self.messages.append(f'{unit.name} 升到了 Lv.{unit.pet.level}！')
                # Keep the battle wrapper in sync, otherwise the round's final
                # _sync_pet writes stale HP/energy over add_exp's level-up gains.
                unit.stats = unit.pet.stats(self.tables)
                unit.base_stats = list(unit.stats)
                unit._apply_talent_stats()
                unit.max_energy = max(1, unit.stats[1])
                unit.hp = min(unit.max_hp, unit.pet.hp)
                unit.energy = min(unit.max_energy, unit.pet.energy)
        # Drops from the original fight row.
        ids = numbers(self.fight_row.get('dropItemIds', '0'))
        pros = numbers(self.fight_row.get('dropPros', '0'))
        counts = numbers(self.fight_row.get('dropItemCounts', '0'))
        for item, probability, count in zip(ids, pros, counts):
            if not item or probability <= 0:
                continue
            if self.rng.randrange(100) < probability:
                amount = max(0, count)
                if amount:
                    self.drops.append((str(item), amount))

    def apply_rewards(self, state):
        if self.rewards_applied:
            return False
        if self.result not in ('win', 'caught'):
            raise ValueError('Only a completed victory or capture can grant rewards')
        messages = []
        with state.transaction():
            from activities import Activities
            from game_formulas import hatch_exp
            Activities(state).add_hatch_exp(hatch_exp(sum(entry[1] for entry in self.exp_gained)))
            state.grant_many([item for item, _ in self.drops],
                             [amount for _, amount in self.drops])
            for item, amount in self.drops:
                row = (self.tables['Pet'].get(str(item)) or
                       self.tables['Item'].get(str(item)) or
                       self.tables['Money'].get(str(item), {}))
                messages.append(f'获得了 {row.get("name", item)} × {amount}。')
            if self.caught_pet:
                name = self.tables['Pet'][self.caught_pet.species]['name']
                state.receive_pet(self.caught_pet)
                messages.append(f'捕捉到了 {name}！')
        self.messages.extend(messages)
        self.rewards_applied = True
        return True

    # -- serialization -------------------------------------------------------
    def snapshot(self):
        return {
            'kind': self.kind, 'name': self.name, 'bgm': self.bgm,
            'can_catch': self.can_catch, 'can_escape': self.can_escape,
            'player': [u.snapshot() for u in self.player],
            'enemy': [u.snapshot() for u in self.enemy],
            'player_index': self.player_index, 'enemy_index': self.enemy_index,
            'round': self.round, 'result': self.result, 'messages': self.messages,
            'force_switch': self.force_switch,
        }


def enemy_pet_spec(tables, key):
    """Turn one NpcPet/BossPet row into the explicit battle specification."""
    key = str(key)
    npc = tables['NpcPet'].get(key)
    if npc:
        return {'species': npc['petId'], 'level': int(npc['level']),
                'skills': numbers(npc.get('skills', '0')),
                'talents': numbers(npc.get('talents', '0')),
                'variation': json.loads(npc['attVar']),
                'growth': json.loads(npc['attUp']),
                'held_item': npc.get('itemId', '0')}
    boss = tables['BossPet'].get(key)
    if boss:
        return {'species': boss['petId'], 'level': int(boss['level']),
                'skills': numbers(boss.get('skills', '0')),
                'talents': numbers(boss.get('talents', '0')),
                'variation': json.loads(boss['attVar']),
                'growth': json.loads(boss['attUp'])}
    raise KeyError(f'未知的原版敌方宠物配置 {key}')


def make_npc_battle(tables, player_pets, npcid, rng):
    row = tables['NpcFight'][str(npcid)]
    specs = [enemy_pet_spec(tables, key) for key in numbers(row['petIds'])]
    kind = 'trainer' if row.get('type') in ('1', '2') else 'boss'
    return Battle(tables, player_pets, specs, rng, kind=kind,
                  name='对手', fight_row=row, bgm=row.get('bgmId', '0'),
                  can_catch=False, can_escape=False)


def make_wild_battle(tables, player_pets, enemy_id, rng):
    row = tables['VillageEnemy'][str(enemy_id)]
    levels = numbers(row.get('levelInterval', '1,1')) or [1, 1]
    level = rng.randint(min(levels), max(levels))
    spec = {'species': row['petId'], 'level': level}
    return Battle(tables, player_pets, [spec], rng, kind='wild',
                  name='野生宠物', fight_row=row,
                  can_catch=True, can_escape=True)
