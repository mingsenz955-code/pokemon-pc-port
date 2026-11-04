"""Regression checks for the complete X 2.10.9 PC data stage."""
from __future__ import annotations

import os
import random
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from battle import make_npc_battle, make_wild_battle
from event_runtime import EventRuntime
from game_state import GameState
from original_data import OriginalData
from pet_factory import generate_pet


class XFullChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = ROOT/'x-data'
        if not (cls.data_dir/'tables.json').is_file():
            raise unittest.SkipTest('x-data is not staged; run tools/stage_x_full.py')
        cls.data = OriginalData(cls.data_dir)
        cls.state = GameState(cls.data.tables)
        cls.state.initialize(1)
        cls.state.add_preset(next(iter(cls.data.tables['InitPet'])))

    def test_complete_data_counts(self):
        tables = self.data.tables
        self.assertEqual(len(tables['VillageMap']), 575)
        self.assertEqual(len(tables['Pet']), 606)
        self.assertEqual(len(tables['Item']), 296)
        self.assertEqual(len(list((self.data_dir/'events').glob('*.json'))), 2320)
        self.assertEqual(len(tables['Skill']), 162)
        self.assertEqual(len(tables['NpcFight']), 500)
        self.assertEqual(len(tables['VillageEnemy']), 668)

    def test_every_map_and_csb_renders(self):
        errors = []
        for key in self.data.tables['VillageMap']:
            try:
                self.data.load_map(key)
            except Exception as error:  # noqa: BLE001 - collect all map failures
                errors.append((key, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])
        ui_errors = []
        from csb_render import CocosUI
        ui = CocosUI(self.data)
        for path in (self.data.assets/'res/UI').glob('*.csb'):
            try:
                ui.render(path.stem, (800, 480))
            except Exception as error:  # noqa: BLE001
                ui_errors.append((path.stem, type(error).__name__, str(error)))
        self.assertFalse(ui_errors, ui_errors[:10])

    def test_every_event_starts_with_original_ids(self):
        runtime = EventRuntime(self.data, self.state)
        errors = []
        for path in (self.data_dir/'events').glob('*.json'):
            if path.name == 'pEventContents.json':
                continue
            try:
                runtime.start(path.name)
                runtime.file, runtime.sequence, runtime.index = '', [], 0
                runtime.pending = None
            except Exception as error:  # noqa: BLE001
                errors.append((path.name, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_every_battle_definition_instantiates(self):
        errors = []
        for key in self.data.tables['NpcFight']:
            try:
                make_npc_battle(self.data.tables, self.state.pets, key, random.Random(7))
            except Exception as error:  # noqa: BLE001
                errors.append((key, type(error).__name__, str(error)))
        for key in self.data.tables['VillageEnemy']:
            try:
                make_wild_battle(self.data.tables, self.state.pets, key, random.Random(7))
            except Exception as error:  # noqa: BLE001
                errors.append((key, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_dialogue_and_text_are_x_data(self):
        rows = self.data.event('pEvent119007.json')
        talks = [row['text'] for row in rows if row.get('type') == 'talk']
        self.assertEqual(talks[:3], ['尼尔:没事了吗？', '克莉丝:嗯、嗯！', '尼尔:走吧！我们去追上达克莱伊。'])
        text = self.data.localized_text()
        self.assertEqual(text['leadName'], '尼尔')
        self.assertIn('leadName2', text)

    def test_malformed_single_talent_probability_does_not_crash(self):
        pet = generate_pet(self.data.tables, random.Random(1), '101025', 150)
        self.assertEqual(pet.species, '101025')
        self.assertTrue(pet.talents)

    def test_x_story_reaches_the_original_battle(self):
        """Play a recovered X scene through its dialogue into its first fight."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.play_event('pEvent119007.json')
                battle = None
                for _ in range(1200):
                    root.update()
                    time.sleep(.002)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk', 'tapscreen'):
                        app.interact()
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.battle:
                        battle = app.battle
                        break
                    elif not app.runtime.running and not app.display_request:
                        break
                self.assertIsNotNone(battle, app.event_issue)
                configured = {row['petId'] for row in self.data.tables['NpcPet'].values()}
                self.assertTrue(battle.enemy)
                self.assertTrue(all(unit.pet.species in configured for unit in battle.enemy))
                self.assertTrue(all(unit.pet.species in self.data.tables['Pet'] for unit in battle.enemy))
                self.assertEqual(app.battle_ui.render().size, (960, 576))
                app.battle_ui.advance(seconds=2)
                self.assertEqual(app.battle_ui.render().size, (960, 576))
                self.assertEqual(app.runtime_error, '')
            finally:
                for job in root.tk.call('after', 'info'):
                    try:
                        root.after_cancel(job)
                    except tk.TclError:
                        pass
                try:
                    root.destroy()
                except tk.TclError:
                    pass

    def test_old_1204_save_restores_into_x(self):
        baseline = ROOT/'original-1.20.4'
        if not (baseline/'tables.json').is_file():
            self.skipTest('1.20.4 baseline is not available')
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                old = NativeGame(root, OriginalData(baseline))
                root.update()
                self.assertTrue(old.save())
                old_map = old.map_id
            finally:
                for job in root.tk.call('after', 'info'):
                    try:
                        root.after_cancel(job)
                    except tk.TclError:
                        pass
                root.destroy()
            root = tk.Tk()
            root.withdraw()
            try:
                app = NativeGame(root, self.data)
                root.update()
                self.assertTrue(app.restore())
                self.assertEqual(app.map_id, old_map)
                self.assertEqual(app.runtime_error, '')
            finally:
                for job in root.tk.call('after', 'info'):
                    try:
                        root.after_cancel(job)
                    except tk.TclError:
                        pass
                root.destroy()

    def test_every_battle_reaches_a_result(self):
        from pet_factory import generate_pet
        pets = [generate_pet(self.data.tables, random.Random(21), '100160', 200)
                for _ in range(3)]
        errors = []
        for maker, table in ((make_npc_battle, 'NpcFight'),
                             (make_wild_battle, 'VillageEnemy')):
            for key in self.data.tables[table]:
                try:
                    battle = maker(self.data.tables, pets, key, random.Random(17))
                    for _ in range(160):
                        if battle.result:
                            break
                        if battle.force_switch:
                            index = next((i for i, unit in enumerate(battle.player)
                                          if unit.alive), None)
                            if index is None:
                                break
                            battle.choose_switch(index)
                        else:
                            battle.choose_skill(0)
                    if not battle.result:
                        errors.append((table, key, 'no result'))
                except Exception as error:  # noqa: BLE001 - collect every battle
                    errors.append((table, key, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_all_x_event_scripts_execute(self):
        """Drive every recovered script through one headless state as a data audit."""
        from event_runtime import EventRuntime
        from game_state import GameState
        errors = []
        for path in sorted((self.data_dir/'events').glob('*.json')):
            if path.name == 'pEventContents.json':
                continue
            state = GameState(self.data.tables)
            state.initialize(1)
            state.add_preset(next(iter(self.data.tables['InitPet'])))
            for key in self.data.tables['Item']:
                state.inventory[key] = 9999
            for key in self.data.tables['Money']:
                state.inventory[key] = 9999999
            runtime = EventRuntime(self.data, state)
            try:
                runtime.start(path.name)
                for _ in range(1000):
                    request = runtime.next()
                    if request is None:
                        if runtime.running:
                            errors.append((path.name, 'stuck'))
                        break
                    if request.kind in ('fight', 'battleover'):
                        runtime.resume('win')
                    elif request.kind == 'costtaskitem':
                        runtime.resume([])
                    elif request.kind == 'accepttask':
                        runtime.resume(True)
                    else:
                        runtime.resume()
                else:
                    errors.append((path.name, 'loop'))
            except Exception as error:  # noqa: BLE001 - collect every script
                errors.append((path.name, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_list_wrapped_x_commands(self):
        """X wraps single fight/fightover/submittask/end parameters in a list."""
        from event_runtime import EventRuntime
        from game_state import GameState
        for filename in ('pEvent1602001.json', 'pEvent1602002.json',
                         'pEvent1602004.json', 'pEvent1602005.json'):
            state = GameState(self.data.tables)
            state.initialize(1)
            state.add_preset(next(iter(self.data.tables['InitPet'])))
            for key in self.data.tables['Item']:
                state.inventory[key] = 9999
            runtime = EventRuntime(self.data, state)
            runtime.start(filename)
            for _ in range(500):
                request = runtime.next()
                if request is None:
                    break
                if request.kind in ('fight', 'battleover'):
                    runtime.resume('win')
                elif request.kind == 'accepttask':
                    runtime.resume(True)
                elif request.kind == 'costtaskitem':
                    runtime.resume([])
                else:
                    runtime.resume()
            self.assertFalse(runtime.running, filename)

    def test_list_wrapped_visual_commands(self):
        from event_runtime import Request
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                root.update()
                requested = []
                app.request_map = requested.append
                app.apply_visual(Request('screen', 'x', 1, {'parameters': [{'type': 0}]}))
                app.apply_visual(Request('screenmove', 'x', 2,
                                         {'parameters': [{'x': 5, 'y': 6, 'speedscale': 0}]}))
                app.apply_visual(Request('tomap', 'x', 3, {'parameters': [{'exit': 910501}]}))
                self.assertTrue(app.screen_black)
                self.assertEqual(requested, [910501])
            finally:
                for job in root.tk.call('after', 'info'):
                    try:
                        root.after_cancel(job)
                    except tk.TclError:
                        pass
                try:
                    root.destroy()
                except tk.TclError:
                    pass

    def test_x_map_npc_trigger_starts_dialogue(self):
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                root.update()
                app.state.main_task, app.state.main_state = 2, 4
                app.state.events['101001'] = 1
                app.load_map(5801)
                app.interact('580101')
                root.update()
                self.assertTrue(app.runtime.running)
                self.assertTrue(app.dialogue)
                self.assertIn('pEvent', app.runtime.file)
                self.assertEqual(app.runtime_error, '')
            finally:
                for job in root.tk.call('after', 'info'):
                    try:
                        root.after_cancel(job)
                    except tk.TclError:
                        pass
                try:
                    root.destroy()
                except tk.TclError:
                    pass

    def test_x_opening_and_battle_start_render(self):
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data, show_opening=True)
                root.update()
                self.assertIsNotNone(app.opening)
                frame = app.make_frame()
                self.assertEqual(frame.size, (960, 576))
                app.opening_input(skip=True)
                root.update()
                self.assertIsNone(app.opening)
                self.assertEqual(app.map_id, 7401)
            finally:
                for job in root.tk.call('after', 'info'):
                    try:
                        root.after_cancel(job)
                    except tk.TclError:
                        pass
                try:
                    root.destroy()
                except tk.TclError:
                    pass

    def test_default_data_root_and_game_boot(self):
        import pc_preview
        old = os.environ.pop('POCKET_NATIVE_DATA', None)
        try:
            self.assertEqual(pc_preview.data_root().resolve(), self.data_dir.resolve())
        finally:
            if old is not None:
                os.environ['POCKET_NATIVE_DATA'] = old
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                root.update()
                frame = app.make_frame()
                self.assertEqual(frame.size, (960, 576))
                self.assertEqual(app.runtime_error, '')
            finally:
                for job in root.tk.call('after', 'info'):
                    try:
                        root.after_cancel(job)
                    except tk.TclError:
                        pass
                try:
                    root.destroy()
                except tk.TclError:
                    pass


if __name__ == '__main__':
    unittest.main(verbosity=2)