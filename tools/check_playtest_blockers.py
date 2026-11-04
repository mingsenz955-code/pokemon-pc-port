"""Regressions reproduced from the five player screenshots, isolated saves."""
import copy
import json
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request
from battle import Battle
from battle_ui import BattleUI

DATA = OriginalData(ROOT/'original-1.20.4')
OUT = ROOT/'outputs/verification/playtest-blockers'
OUT.mkdir(parents=True, exist_ok=True)


class PlaytestBlockers(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
        os.environ['POCKET_NATIVE_SAVE_DIR'] = self.folder.name
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.app = NativeGame(self.root, DATA)
        a = self.app
        a.runtime.file, a.runtime.sequence, a.runtime.pending = '', [], None
        a.display_request, a.dialogue, a.pending_wait = None, None, None
        a.state.initialize(1)
        a.state.add_preset(1)
        a.guide.rebind(a.state)

    def tearDown(self):
        if self.app.ui_window and self.app.ui_window.winfo_exists():
            self.app.ui_window.destroy()
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.folder.cleanup()
        if self.previous is None:
            os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
        else:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = self.previous
        self.assertEqual([], self.errors)

    def battle(self):
        a = self.app
        enemy = copy.deepcopy(a.state.pets[0])
        enemy.uid = 'wild-enemy'
        enemy.talents = []
        a.state.pets[0].talents = []
        b = Battle(DATA.tables, a.state.pets, [enemy], a.state.rng, kind='wild')
        b.player_active.hp = b.player_active.max_hp = 1000
        b.enemy_active.hp = b.enemy_active.max_hp = 1000
        b.enemy_active.pet.skills = ['300056', '300071']
        a.battle, a.battle_ui = b, BattleUI(a, b)
        return b, a.battle_ui

    def press_battle(self, ui, key):
        ui.frame = None
        ui.render()
        rect = ui.hits[key]
        return ui.click((rect[0]+rect[2])/2, (rect[1]+rect[3])/2)

    def test_starter_hover_preserves_pet_stats_and_no_payment_samples(self):
        a = self.app
        a.state.initialize(1)
        a.open_ui(Request('openui', 'starter-test', 1, {'parameters': {'uiid': 7, 'par1': 1}}))
        a.ui_window.withdraw()
        page = a.original_page
        self.assertEqual('ChooseFirstPetUI', page.specs[0][0])
        self.assertTrue(any(s[0] == 'PetPropertyItemUI' for s in page.specs))
        self.assertFalse(any(k.endswith('/costTip_Text') for k in a.ui_rects))
        key = next(k for k in a.ui_buttons if k.endswith('/confirm_Button'))
        before, after = page.display_frame.copy(), page.feedback(key)
        box = ImageChops.difference(before, after).convert('RGB').getbbox()
        if box:
            rect = a.ui_buttons[key]
            self.assertGreaterEqual(box[0], round(rect[0])-1)
            self.assertLessEqual(box[2], round(rect[2])+1)
        page.display_frame.save(OUT/'starter.png')
        rect = a.ui_buttons[key]
        event = SimpleNamespace(x=(rect[0]+rect[2])/2, y=(rect[1]+rect[3])/2)
        a.on_ui_press(event)
        a.on_ui_release(event)
        self.assertEqual(1, a.state.starter_id)
        self.assertEqual(1, len(a.state.pets))

    def test_all_balls_success_render_and_return_without_refresh_exception(self):
        a = self.app
        for item in ('220004', '220005', '220006'):
            b, ui = self.battle()
            b.can_catch = True
            a.state.inventory = {item: 2}
            ui.screen = 'balls'
            with patch.object(b, 'capture_chance', return_value=100):
                self.press_battle(ui, 'itemMenu_1_Button')
            self.assertEqual('caught', b.result)
            self.assertEqual(1, a.state.count(item))
            ui.advance(seconds=20)
            ui.render().save(OUT/(item+'-caught.png'))
            a.tick()
            self.assertEqual([], self.errors)
            actions = []
            for _ in range(8):
                action = self.press_battle(ui, 'result_continue')
                actions.append(action)
                if action == 'finish':
                    break
            self.assertEqual('finish', actions[-1])
            a.finish_battle()
            self.assertIsNone(a.battle)

    def test_failed_capture_includes_enemy_attack_and_accepts_next_click(self):
        a = self.app
        b, ui = self.battle()
        b.can_catch = True
        a.state.inventory = {'220004': 2}
        ui.screen = 'balls'
        before = b.player_active.hp
        with patch.object(b, 'capture_chance', return_value=1), patch.object(b.rng, 'randint', return_value=100):
            self.press_battle(ui, 'itemMenu_1_Button')
        self.assertTrue(any(e['type'] == 'catch_failed' for e in b.events))
        self.assertLess(b.player_active.hp, before)
        self.assertEqual(1, a.state.count('220004'))
        ui.advance(seconds=20)
        ui.render().save(OUT/'capture-failed.png')
        self.assertIsNone(ui.anim)
        self.assertIsNone(b.result)
        rect = ui.target_hits['enemyMenuPos_Panel']
        ui.click((rect[0]+rect[2])/2, (rect[1]+rect[3])/2)
        self.assertEqual('skills', ui.screen)

    def test_enemy_first_turn_is_normal_attack_not_random_idle(self):
        b, ui = self.battle()
        before = b.player_active.hp
        b.choose_skill(0)
        ui._capture_events()
        self.assertLess(b.player_active.hp, before)
        self.assertTrue(any(e['type'] == 'attack' and e['side'] == 'enemy' for e in b.events))
        sides = [ui.anim['side']]+[a['side'] for a in ui.anim_queue]
        self.assertIn('player', sides)
        self.assertIn('enemy', sides)
        ui.advance(seconds=20)
        self.assertIsNone(ui.anim)

    def test_normal_settlement_never_renders_world_boss_card(self):
        b, ui = self.battle()
        b.player_active.participated = True
        b.enemy_active.hp = 0
        b._check_end()
        seen = []
        original = self.app.cocos_ui.render
        def record(name, *args, **kwargs):
            seen.append(name)
            return original(name, *args, **kwargs)
        with patch.object(self.app.cocos_ui, 'render', side_effect=record):
            ui.render().save(OUT/'win.png')
            self.press_battle(ui, 'result_continue')
            ui.render().save(OUT/'calculation.png')
        self.assertIn('ChallengeResultUI', seen)
        self.assertIn('BattleCalculationUI', seen)
        self.assertNotIn('WorldMonsterBattleResultUI', seen)

    def test_obsolete_and_missing_button_tips_are_skipped_but_story_remains(self):
        a = self.app
        a.runtime.file = 'playtest-tutorial'
        a.runtime.sequence = [
            {'id': 1, 'type': 'button', 'nodekey': 'mainUp_Button', 'text': '旧商店列表教程'},
            {'id': 2, 'type': 'button', 'nodekey': 'nonexistent_Button', 'text': '不存在的按钮'},
            {'id': 3, 'type': 'talk', 'text': '尼尔:该去商店了。'}]
        a.runtime.index = 0
        a.drive()
        self.assertEqual('button', a.display_request.kind)
        self.assertIn('nonexistent_Button', a.event_issue)
        # A missing real tutorial node must not silently advance the story;
        # obsolete mainUp was skipped, but this request remains visible.
        a.display_request = None
        a.runtime.resume()
        a.drive()
        self.assertEqual('talk', a.display_request.kind)
        self.assertIn('该去商店', a.dialogue)

    def test_tutorial_click_requires_the_actual_visible_target(self):
        a = self.app
        a.load_map(101, 1248, 1504)
        a.screen_black = False
        a.runtime.file = 'playtest-tutorial'
        a.runtime.sequence = [{'id': 1, 'type': 'button', 'nodekey': 'uiDisappear_Button', 'text': '点击隐藏按钮'},
                              {'id': 2, 'type': 'talk', 'text': '尼尔:完成。'}]
        a.runtime.index = 0
        a.drive()
        self.assertEqual('button', a.display_request.kind)
        a.on_click(SimpleNamespace(x=450, y=300))
        self.assertEqual('button', a.display_request.kind)
        a.make_frame().save(OUT/'tutorial-target.png')
        r = a.scene_ui.hits['uiDisappear_Button']
        a.on_click(SimpleNamespace(x=(r[0]+r[2])/2, y=(r[1]+r[3])/2))
        self.assertEqual('talk', a.display_request.kind)
        self.assertTrue(a.scene_ui.hidden)

    def test_render_cache_and_frame_time_report(self):
        b, ui = self.battle()
        times = []
        for i in range(30):
            ui.advance(seconds=1/60)
            start = time.perf_counter()
            ui.render()
            times.append((time.perf_counter()-start)*1000)
        self.assertLessEqual(len(ui._hud_cache), 8)
        self.assertLessEqual(len(ui._pose_cache), 64)
        (OUT/'frame-times.json').write_text(json.dumps({'cold_mean_ms': sum(times[:15])/15,
            'warm_mean_ms': sum(times[15:])/15, 'max_ms': max(times), 'target_fps': self.app.TARGET_FPS}, indent=2), encoding='utf-8')

    def test_higher_pose_sampling_keeps_the_same_animation_time(self):
        species = self.app.state.pets[0].species
        low = DATA.pet_frame(species, 'attack', 6, loop=False, fps=12)
        high = DATA.pet_frame(species, 'attack', 15, loop=False, fps=30)
        self.assertEqual(low.size, high.size)
        self.assertEqual(low.tobytes(), high.tobytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
