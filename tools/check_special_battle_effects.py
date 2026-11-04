"""Replay real skills against native ExportJson callback frames, no player saves."""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from battle import Battle
from battle_ui import BattleUI
from battle_effects import BattleEffects
from csb_render import CocosUI

DATA = OriginalData(ROOT/'original-1.20.4')
OUT = ROOT/'outputs/verification/special-battle-effects'
OUT.mkdir(parents=True, exist_ok=True)


def host(seed=42):
    state = GameState(DATA.tables, seed)
    pet = copy.deepcopy(state.pets[0])
    pet.talents = []
    enemy = copy.deepcopy(pet)
    enemy.uid = 'enemy'
    battle = Battle(DATA.tables, [pet], [enemy], state.rng)
    for unit in battle.player+battle.enemy:
        unit.hp = unit.max_hp = 10000
        unit.energy = unit.max_energy = 1000
    app = SimpleNamespace(data=DATA, state=state, cocos_ui=CocosUI(DATA), battle_tips=[])
    return battle, BattleUI(app, battle)


class SpecialEffects(unittest.TestCase):
    def test_all_six_effect_classes_have_real_animation_plans(self):
        effects = BattleEffects(DATA)
        supported = set()
        for key, row in DATA.tables['Skill'].items():
            effect = DATA.tables['SkillEffect'].get(row.get('skillEffectTypeId'))
            if not effect:
                continue
            plan = effects.plan(key, 'player')
            self.assertIsNotNone(plan, key)
            self.assertTrue(DATA.armature_source(plan['path'])[1], key)
            self.assertEqual(int(row['effectpos']) == 2, plan['self_target'])
            self.assertEqual(plan['path'], effects.plan(key, 'enemy')['path'])
            supported.add(plan['type'])
        self.assertEqual(set(range(6)), supported)

    def test_wind_loads_front_and_rear_for_both_sides(self):
        battle, ui = host()
        for side in ('player', 'enemy'):
            plan = ui.effects.plan('300030', side)
            self.assertEqual(('kuangfeng_q', 'kuangfeng_h'), (plan['path'], plan['rear_path']))
            self.assertFalse(plan['self_target'])
            ui.anim = {'effect': plan, 'side': side, 'age': 6, 'kind': 'skill', 'target': '', 'amount': 0}
            front, rear = [Image.new('RGBA', (960, 576)) for _ in range(2)]
            ui.effects.draw(front, ui)
            ui.effects.draw(rear, ui, rear=True)
            self.assertIsNotNone(front.getbbox())
            self.assertIsNotNone(rear.getbbox())
            self.assertIsNotNone(ImageChops.difference(front, rear).getbbox())

    def test_tornado_six_hits_apply_only_at_each_authored_frame(self):
        battle, ui = host()
        battle._use_skill(battle.player_active, battle.enemy_active, DATA.tables['Skill']['300033'])
        damages = [e for e in battle.events if e['type'] == 'damage']
        self.assertEqual(list(range(6)), [e['hit_index'] for e in damages])
        ui._capture_events()
        self.assertEqual(tuple(f*25/60 for f in (5, 40, 80, 120, 160, 200)), ui.anim['effect']['hits'])
        key = ('enemy', battle.enemy_active.pet.uid)
        for event, frame in zip(damages, (5, 40, 80, 120, 160, 200)):
            previous = ui.visual_hp[key]
            when = frame*25/60
            ui.advance(when-ui.anim['age']-.001)
            self.assertEqual(previous, ui.visual_hp[key])
            ui.advance(.002)
            self.assertEqual(event['hp'], ui.visual_hp[key])
            self.assertEqual(event['amount'], ui.anim['impact']['amount'])
        ui.render().save(OUT/'tornado-sixth-hit.png')

    def test_skipped_multi_hit_keeps_its_original_callback_slot(self):
        battle, ui = host()
        battle.events = [{'type': 'skill', 'side': 'player', 'uid': battle.player_active.pet.uid,
                          'skill_id': '300033'},
                         {'type': 'damage', 'side': 'enemy', 'uid': battle.enemy_active.pet.uid,
                          'hp': 9900, 'amount': 100, 'hit_index': 2}]
        ui._capture_events()
        key = ('enemy', battle.enemy_active.pet.uid)
        ui.advance(79*25/60)
        self.assertEqual(10000, ui.visual_hp[key])
        ui.advance(2*25/60)
        self.assertEqual(9900, ui.visual_hp[key])

    def test_heal_is_visible_on_self_at_add_callback(self):
        battle, ui = host()
        unit = battle.player_active
        unit.hp = 100
        key = ('player', unit.pet.uid)
        ui.visual_hp[key] = ui.display_hp[key] = 100
        battle._use_skill(unit, battle.enemy_active, DATA.tables['Skill']['300047'])
        ui._capture_events()
        self.assertTrue(ui.anim['effect']['self_target'])
        ui.advance(4.99*25/60)
        self.assertEqual(100, ui.visual_hp[key])
        ui.advance(.02)
        self.assertEqual(unit.hp, ui.visual_hp[key])
        self.assertEqual('heal', ui.anim['impact']['type'])
        ui.render().save(OUT/'heal-add-frame.png')

    def test_slow_render_does_not_skip_final_hp_or_double_apply_damage(self):
        battle, ui = host()
        battle._use_skill(battle.player_active, battle.enemy_active, DATA.tables['Skill']['300033'])
        ui._capture_events()
        final, rng = battle.enemy_active.hp, battle.rng.getstate()
        ui.advance(seconds=12)
        self.assertIsNone(ui.anim)
        self.assertEqual(final, ui.visual_hp[('enemy', battle.enemy_active.pet.uid)])
        self.assertEqual(final, battle.enemy_active.hp)
        self.assertEqual(rng, battle.rng.getstate())

    def test_sound_plays_once_at_exact_authored_frame(self):
        battle, ui = host()
        ui.app.root = object()
        played = []
        ui.effect_audio.play = played.append
        battle._use_skill(battle.player_active, battle.enemy_active, DATA.tables['Skill']['300030'])
        ui._capture_events()
        ui.advance(4*25/60)
        self.assertEqual(['kuangfeng.mp3'], played)
        ui.advance(10)
        self.assertEqual(['kuangfeng.mp3'], played)

    def test_six_classes_render_original_art_without_consuming_random_state(self):
        sheet = Image.new('RGB', (960, 864))
        for i, key in enumerate(('300001', '300030', '300004', '300003', '300033', '300047')):
            battle, ui = host()
            rng = battle.rng.getstate()
            plan = ui.effects.plan(key, 'player')
            ui.anim = {'effect': plan, 'side': 'player', 'age': 15*25/60, 'kind': 'skill',
                       'duration': plan['duration'], 'hit_at': plan['hit'], 'target': '', 'amount': 0}
            frame = ui.render().convert('RGB').resize((480, 288))
            ImageDraw.Draw(frame).text((5, 5), f"effectType={plan['type']} {key}", fill='white')
            sheet.paste(frame, ((i%2)*480, (i//2)*288))
            self.assertEqual(rng, battle.rng.getstate())
        sheet.save(OUT/'six-classes.png')


if __name__ == '__main__':
    unittest.main(verbosity=2)
