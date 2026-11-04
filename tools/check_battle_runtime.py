"""Deterministic checks for the native battle core and capture path."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from battle import make_npc_battle, make_wild_battle

data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables, 12345)
state.initialize(2)
battle = make_npc_battle(data.tables, state.pets, 1002011, random.Random(7))
rounds = 0
while not battle.result and rounds < 60:
    rounds += 1
    if battle.force_switch:
        battle.choose_switch(next(i for i, unit in enumerate(battle.player) if unit.alive))
    else:
        battle.choose_skill(0)
assert battle.result in ('win', 'lose'), battle.result
assert battle.round > 0
print('npc', battle.result, battle.round, battle.exp_gained[:2])

state = GameState(data.tables, 54321)
state.initialize(1)
state.add_preset(201)
state.inventory['220004'] = 20
wild = make_wild_battle(data.tables, state.pets, 607001, random.Random(11))
chance_full = wild.capture_chance('220004')
wild.enemy_active.hp = 1
chance_low = wild.capture_chance('220004')
assert 1 <= chance_full <= 100 and chance_low >= chance_full, (chance_full, chance_low)
rounds = 0
while not wild.result and rounds < 80:
    rounds += 1
    if wild.force_switch:
        wild.choose_switch(next(i for i, unit in enumerate(wild.player) if unit.alive))
    else:
        wild.choose_item('220004')
assert wild.result in ('caught', 'win', 'lose', 'escape'), wild.result
if wild.result == 'caught':
    wild.apply_rewards(state)
    assert str(wild.caught_pet.species) in [p.species for p in state.pets+state.bank]
print('wild', wild.result, wild.round, chance_full, chance_low)

report = {'npc_battle': battle.result, 'rounds': battle.round,
          'capture_full_hp': chance_full, 'capture_1hp': chance_low,
          'wild_battle': wild.result}
(ROOT/'outputs/verification/battle-runtime-checks.json').write_text(
    __import__('json').dumps(report, indent=2), encoding='utf-8')
print(report)
