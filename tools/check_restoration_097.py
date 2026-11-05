"""Behavior, authored blending and timing regressions for X battle restoration."""
import copy
import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from armature_composite import additive_composite, composite, transform_art
from battle import Battle
from battle_ui import BattleUI
from battle_effects import BattleEffects
from ccs_timeline import sample_frame, easing
from csb_render import CocosUI
from game_state import GameState
from original_data import OriginalData
from pc_game import NativeGame
from spine_renderer import atlas_regions

DATA = OriginalData(ROOT/'x-data')
OUT = ROOT/'outputs/verification/0.2.97'
OUT.mkdir(parents=True, exist_ok=True)


def host(opening=False):
    state = GameState(DATA.tables, 97)
    pet = copy.deepcopy(state.pets[0])
    enemy = copy.deepcopy(pet)
    enemy.uid = 'enemy-97'
    battle = Battle(DATA.tables, [pet], [enemy], state.rng)
    battle.kind = 'wild'
    app = SimpleNamespace(data=DATA, state=state, cocos_ui=CocosUI(DATA), battle_tips=[])
    return BattleUI(app, battle, opening=opening)


class Restoration(unittest.TestCase):
    def test_repel_blocks_even_overdue_encounters_and_preserves_rng(self):
        app = NativeGame.__new__(NativeGame)
        app.data, app.state = DATA, GameState(DATA.tables, 97)
        app.battle = app.ui_open = app.display_request = app.pending_wait = None
        app.runtime = SimpleNamespace(running=False)
        app.map_id = next(k for k, v in DATA.tables['VillageMap'].items()
                          if v.get('enemyIds', '0') != '0')
        app.encounter_threshold = 30
        app.save = lambda: None
        app.pick_wild_enemy = lambda ids, weights: ids[0]
        calls = []
        app.start_battle = lambda *args: calls.append(args) or True
        for kid in ('220002', '220010'):
            app.state.inventory[kid] = 1
            app.encounter_distance = 10**8
            app.use_perfume(kid)
            self.assertEqual(0, app.state.count(kid))
            self.assertEqual(0, app.encounter_distance)
            rng = app.state.rng.getstate()
            for _ in range(10):
                app.encounter_distance = 10**8
                self.assertFalse(app.check_encounter())
            self.assertEqual([], calls)
            self.assertEqual(rng, app.state.rng.getstate())
            # Old saved buffs lack a new flag: item/steps/until suffice.
            app.state.activities['perfume']['until'] = time.time()-1
            app.encounter_distance = 10**8
            self.assertTrue(app.check_encounter())
            calls.clear()
        app.state.inventory['220003'] = 1
        app.use_perfume('220003')
        app.encounter_distance = 10**8
        self.assertTrue(app.check_encounter())
        self.assertEqual('220003', app.state.activities['perfume']['item'])

    def test_all_recovered_easing_types_move_between_keys(self):
        for kind in (-1, 0, 1, 2, 3, 4, 5, 7, 8, 10, 14, 15, 19, 20):
            with self.subTest(kind=kind):
                first = {'fi': 0, 'x': 0, 'twE': kind,
                         'twEP': [0, 0, .2, .8, .8, .9, 1, 1]}
                sample = sample_frame([first, {'fi': 10, 'x': 100}], 5)
                self.assertGreater(sample['x'], 0)
                self.assertLess(sample['x'], 100)
        self.assertAlmostEqual(.25, easing(.5, 4))
        self.assertAlmostEqual(.75, easing(.5, 5))
        self.assertEqual(0, sample_frame([{'fi': 0, 'x': 0, 'tweenFrame': False},
                                        {'fi': 10, 'x': 100}], 5)['x'])

    def test_additive_glow_adds_light_and_preserves_transparent_edges(self):
        dest = Image.new('RGBA', (2, 2), (100, 80, 60, 255))
        additive_composite(dest, Image.new('RGBA', (2, 2), (200, 100, 50, 128)), (0, 0))
        self.assertEqual((200, 130, 85, 255), dest.getpixel((0, 0)))
        empty = Image.new('RGBA', (2, 2))
        additive_composite(empty, Image.new('RGBA', (2, 2), (200, 100, 50, 128)), (0, 0))
        self.assertEqual(128, empty.getpixel((0, 0))[3])
        self.assertGreaterEqual(empty.getpixel((0, 0))[0], 198)

    def test_skill_layers_use_authored_modes_on_world_background(self):
        effects = BattleEffects(DATA)
        found = False
        for key in DATA.tables['Skill']:
            plan = effects.plan(key, 'player')
            if not plan:
                continue
            art = effects._scaled_art(plan['path'], int(plan['duration']*60/25/2), 1.2)
            if art and any(add for _, _, add in art.info.get('blend_layers', ())):
                found = True
                dest = Image.new('RGBA', art.size, (90, 80, 70, 255))
                flat = dest.copy()
                flat.alpha_composite(art)
                composite(dest, art, (0, 0))
                self.assertIsNotNone(ImageChops.difference(dest.convert('RGB'), flat.convert('RGB')).getbbox())
                turned = transform_art(art, .75, rotate=True)
                self.assertTrue(turned.info['blend_layers'])
                break
        self.assertTrue(found)

    def test_item_effect_type_zero_is_valid(self):
        effects = BattleEffects(DATA)
        key = next(k for k, r in DATA.tables['SkillEffect'].items()
                   if r.get('effectType') == '0' and DATA.armature_source(r['path1'])[1])
        self.assertEqual(0, effects.plan_effect(key)['type'])

    def test_escape_is_visible_and_queued_after_previous_attack(self):
        ui = host()
        unit = ui.battle.enemy_active
        unit.fled = True
        ui.battle.events = [
            {'type': 'attack', 'side': 'player', 'uid': ui.battle.player_active.pet.uid, 'skill_id': '300056'},
            {'type': 'enemy_escape', 'name': unit.name}]
        ui._event_batch = None
        ui._capture_events()
        self.assertEqual('attack', ui.anim['kind'])
        self.assertEqual('escape', ui.anim_queue[-1]['kind'])
        layer = Image.new('RGBA', (960, 576))
        ui._draw_pet(layer, unit, (700, 390), 235, True)
        self.assertIsNotNone(layer.getbbox())
        ui.advance(ui.anim['duration'])
        self.assertEqual('escape', ui.anim['kind'])
        layer = Image.new('RGBA', (960, 576))
        ui._draw_pet(layer, unit, (700, 390), 235, True)
        self.assertIsNotNone(layer.getbbox())
        ui.anim['age'] = 10
        self.assertEqual((480, 0), ui._animation_offsets()[0])
        ui.advance(.01)
        layer = Image.new('RGBA', (960, 576))
        ui._draw_pet(layer, unit, (700, 390), 235, True)
        self.assertIsNone(layer.getbbox())

    def test_failed_escape_returns_in_point_four_seconds(self):
        ui = host()
        ui.anim = {'kind': 'escape_failed', 'side': 'player', 'age': 5, 'duration': 10}
        self.assertLess(ui._animation_offsets()[0][1], 0)
        ui.anim['age'] = 10
        self.assertEqual((0, 0), ui._animation_offsets()[0])

    def test_wild_enemy_is_present_before_player_ball_opens(self):
        ui = host(opening=True)
        ui.opening_frame = ui.opening_transition+5
        for enemy in (False, True):
            layer = Image.new('RGBA', (960, 576))
            ui._draw_pet(layer, ui.presentation_unit(enemy), (500, 400), 235, enemy)
            self.assertEqual(enemy, layer.getbbox() is not None)

    def test_entry_uses_native_five_clip_sequence_and_out_frame(self):
        ui = host(opening=True)
        plan = ui._entry_plan('player')
        self.assertEqual(['Animation6', 'Animation2', 'Animation1', 'Animation3', 'Animation5'],
                         [s[0] for s in plan['segments']])
        self.assertEqual(94, plan['reveal'])
        self.assertEqual(209, plan['duration'])
        self.assertEqual('Animation8_0.8', ui._entry_plan('enemy')['segments'][0][0])
        self.assertEqual((0, 0, 0), ui._appearance_pose(-1))
        self.assertGreater(ui._appearance_pose(18)[1], 100)
        self.assertEqual((1, 0, 1), ui._appearance_pose(78))

    def test_queued_cast_sound_waits_for_its_own_animation(self):
        ui = host()
        played = []
        ui.app.root = object()
        ui.effect_audio = SimpleNamespace(play=played.append)
        ui.battle.events = [{'type': 'skill', 'side': side, 'skill_id': '300030',
                             'uid': unit.pet.uid} for side, unit in
                            [('player', ui.battle.player_active), ('enemy', ui.battle.enemy_active)]]
        ui._event_batch = None
        ui._capture_events()
        self.assertEqual([], played)
        ui.advance(.1)
        self.assertEqual(1, played.count('4030'))
        ui.advance(ui.anim['duration']-ui.anim['age']+.1)
        self.assertEqual(2, played.count('4030'))

    def test_atlas_decodes_each_page_once(self):
        paths = list((DATA.assets/'Sprite').rglob('*.atlas'))
        if not paths:
            paths = list(DATA.assets.rglob('*.atlas'))
        path = max(paths, key=lambda p: p.stat().st_size)
        atlas_regions.cache_clear()
        real_open = Image.open
        calls = []
        def observe(path, *args, **kwargs):
            calls.append(str(path))
            return real_open(path, *args, **kwargs)
        with patch('spine_renderer.Image.open', observe):
            regions = atlas_regions(path)
        self.assertGreater(len(regions), len(calls))
        self.assertEqual(len(calls), len(set(calls)))

    def test_baked_skill_layers_match_live_render_pixels(self):
        from battle_animation_cache import NAMES, cached_frame
        for name in NAMES:
            _, source = DATA.armature_source(name)
            duration = next(m['dr'] for m in source['animation_data'][0]['mov_data'] if m['name'] == 'Animation1')
            for index in (0, duration//2, duration-1):
                direct = DATA.armature(name, 'Animation1', index, layered=True)
                baked = cached_frame(DATA, name, index, 1.2)
                if direct is None:
                    self.assertIsNone(baked)
                    continue
                self.assertIsNotNone(baked)
                direct = transform_art(direct, 1.2)
                self.assertEqual(direct.info['origin'], baked.info['origin'])
                a = Image.new('RGBA', direct.size, (70, 90, 110, 255))
                b = a.copy()
                composite(a, direct, (0, 0))
                composite(b, baked, (0, 0))
                self.assertIsNone(ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox(), (name, index))

    def test_result_timer_waits_for_final_effect(self):
        ui = host()
        ui.battle.result = 'win'
        ui.anim = {'kind': 'damage', 'side': '', 'target': '', 'age': 0,
                   'duration': 10, 'damages': []}
        ui.advance(5)
        self.assertEqual(0, ui.result_age)
        ui.advance(5)
        self.assertIsNone(ui.anim)
        ui.advance(1)
        self.assertGreater(ui.result_age, 0)


def visuals():
    ui = host(opening=True)
    sheet = Image.new('RGB', (1440, 864), 'white')
    for index, age in enumerate((5, 75, 112, 180)):
        ui.opening_frame = ui.opening_transition+age
        ui.frame = None
        shot = ui.render().convert('RGB').resize((480, 288))
        ImageDraw.Draw(shot).text((8, 8), f'Wild entry frame {age}', fill='white')
        sheet.paste(shot, ((index%3)*480, (index//3)*288))
    ui.opening_frame = None
    for index, skill in enumerate(('300030', '300033', '300001', '300004', '300047'), 4):
        plan = ui.effects.plan(skill, 'player')
        ui.anim = {'kind': 'skill', 'side': 'player', 'target': 'enemy', 'effect': plan,
                   'age': min(15, plan['duration']/2), 'amount': 0, 'duration': plan['duration']}
        ui.frame = None
        shot = ui.render().convert('RGB').resize((480, 288))
        ImageDraw.Draw(shot).text((8, 8), f'Skill {skill}', fill='white')
        sheet.paste(shot, ((index%3)*480, (index//3)*288))
    sheet.save(OUT/'battle-contact-sheet.jpg', quality=92)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Restoration))
    if result.wasSuccessful():
        visuals()
    (OUT/'regressions.json').write_text(json.dumps({'tests': result.testsRun, 'failures': len(result.failures),
                                                   'errors': len(result.errors)}), encoding='utf-8')
    sys.exit(not result.wasSuccessful())
