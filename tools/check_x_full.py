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