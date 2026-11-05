"""Regression checks for the complete X 2.10.9 PC data stage."""
from __future__ import annotations

import os
import random
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from battle import Buff, make_npc_battle, make_wild_battle
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

    def test_x_talent_passives(self):
        """Passive talent state codes parse into combat modifiers."""
        pet = generate_pet(self.data.tables, random.Random(41), '100160', 80)
        pet.talents = ['400121', '400214', '400215', '400216', '400217',
                       '400117', '400122', '400136', '400137', '400138',
                       '400140', '400141', '400206', '400208', '400134', '400135',
                       '400144', '400146', '400145', '400127', '400128', '400129',
                       '400131', '400132', '400201', '400202', '400213']
        battle = make_wild_battle(self.data.tables, [pet],
                                  next(iter(self.data.tables['VillageEnemy'])),
                                  random.Random(42))
        unit = battle.player[0]
        self.assertAlmostEqual(20, unit.crit_bonus)
        self.assertAlmostEqual(30, unit.half_damage_chance)
        self.assertAlmostEqual(15, unit.damage_up)
        self.assertAlmostEqual(15, unit.damage_down)
        self.assertAlmostEqual(10, unit.regen_pct)
        self.assertAlmostEqual(25, unit.talent_chance['2'])
        self.assertAlmostEqual(10, unit.dot_up['2'])
        self.assertAlmostEqual(25, unit.talent_resist['13'])
        self.assertIn('9', unit.talent_immune)
        self.assertTrue(battle._immune(unit, '9'))
        self.assertFalse(battle._immune(unit, '2'))
        self.assertTrue(unit.prevent_drain)
        self.assertTrue(unit.ignore_invincible)
        self.assertEqual('hp', unit.convert_damage['defence'])
        self.assertEqual('energy', unit.convert_damage['energy'])
        self.assertEqual(25, unit.reflect_damage['energy'])
        self.assertEqual(20, unit.capture_bonus)
        self.assertEqual(25, unit.escape_bonus)
        self.assertEqual(5, unit.dodge_chance)
        self.assertTrue(unit.never_miss)
        self.assertTrue(unit.cleanse_on_switch)
        self.assertTrue(unit.copy_status_on_switch)
        self.assertEqual(200, unit.opponent_energy_penalty)
        self.assertEqual(100, unit.reflect_damage['power'])
        self.assertEqual(30, unit.talent_boost[3])
        self.assertEqual(200, unit.low_hp_boost)
        self.assertEqual(35, unit.poison_skin)
        self.assertTrue(unit.last_stand)
        self.assertEqual(100, unit.revive_percent)
        self.assertEqual(2.0, unit.exp_multiplier)
        self.assertEqual('2', unit.terrain_override)
        enemy = battle.enemy[0]
        unit.hp = 10
        battle._deal(enemy, unit, 9999, 'power')
        self.assertEqual(1, unit.hp)
        self.assertTrue(unit.last_stand_used)
        unit.poison_skin = 100
        battle._deal(enemy, unit, 9999, 'power')
        self.assertEqual(unit.max_hp, unit.hp)
        self.assertTrue(unit.revive_used)
        self.assertTrue(enemy.has_state('2'))
        enemy.hp = enemy.max_hp
        chance_with = battle.capture_chance('220004')
        unit.capture_bonus = 0
        self.assertEqual(chance_with-20, battle.capture_chance('220004'))
        skill = next(row for row in self.data.tables['Skill'].values()
                     if int(row.get('energyCost', 0) or 0) > 0)
        enemy = battle.enemy[0]
        base_cost = enemy.cost(skill)
        enemy.energy = enemy.max_energy
        before_energy = enemy.energy
        battle._use_skill(enemy, unit, skill)
        self.assertEqual(base_cost*3, before_energy-enemy.energy)
        unit.energy = 1
        energy_before = unit.energy
        battle._deal(battle.enemy[0], unit, 20, 'energy')
        self.assertGreater(unit.energy, energy_before)
        enemy = battle.enemy[0]
        enemy.hp = enemy.max_hp
        enemy.add_buff('45', Buff('45', 3, '41,1', 1, '', '力量伤害无效'))
        unit.ignore_invincible = False
        battle._deal(unit, enemy, 50, 'power')
        self.assertEqual(enemy.max_hp, enemy.hp)
        unit.ignore_invincible = True
        battle._deal(unit, enemy, 50, 'power')
        self.assertLess(enemy.hp, enemy.max_hp)
        self.assertEqual(85, battle._reduce_talent_damage(100, unit))
        unit.hp = max(1, unit.max_hp//2)
        before = unit.hp
        battle._end_round()
        self.assertGreater(unit.hp, before)

    def test_x_state_targets_follow_buff_type(self):
        from battle import SELF_STATES
        wrong = []
        for key, row in self.data.tables['SkillState'].items():
            buff_type = int(row.get('buffType', 0) or 0)
            if buff_type == 1 and int(key) not in SELF_STATES:
                wrong.append((key, 'buff1-not-self'))
            if buff_type == 2 and int(key) in SELF_STATES:
                wrong.append((key, 'debuff-self'))
        self.assertFalse(wrong, wrong)

    def test_x_switch_talent_cleanse_and_copy(self):
        """Natural Recovery cleanses on switch-out; Mirror Effect copies buffs."""
        pet = generate_pet(self.data.tables, random.Random(51), '100160', 80)
        pet.talents = ['400144']
        copied = generate_pet(self.data.tables, random.Random(52), '100160', 80)
        copied.talents = ['400146', '400207']
        battle = make_wild_battle(self.data.tables, [pet, copied],
                                  next(iter(self.data.tables['VillageEnemy'])),
                                  random.Random(53))
        old = battle.player[0]
        old.add_buff('2', Buff('2', 3, '9,15', 2, '', '中毒'))
        battle.enemy[0].add_buff('11', Buff('11', 3, '27,25', 1, '', '力量增强'))
        battle._switch(old, 1)
        self.assertFalse(old.has('poison'))
        self.assertTrue(any(buff.key == '11' for buff in battle.player[1].buffs))
        self.assertTrue(battle.player[1].off_field_exp)
        bench_name = battle.player[1].name
        old.participated = True
        battle._award()
        self.assertTrue(any(name == bench_name for name, _, _ in battle.exp_gained))

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

    def test_battle_result_lists_level_up(self):
        from types import SimpleNamespace
        from battle_ui import BattleUI
        battle = SimpleNamespace(exp_gained=[('皮卡丘', 120, [10, 11])], drops=[],
                                 result='win', caught_pet=None)
        fake = SimpleNamespace(battle=battle, app=SimpleNamespace(data=self.data))
        lines = BattleUI._result_lines(fake)
        self.assertIn('皮卡丘 获得 120 点经验。', lines)
        self.assertIn('皮卡丘 升到了 Lv.11！', lines)

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

    def test_x_all_abnormal_talents(self):
        """State 58 is the all-abnormal resistance used by holy/divine talents."""
        enemy = next(iter(self.data.tables['VillageEnemy']))
        holy = generate_pet(self.data.tables, random.Random(61), '100160', 80)
        holy.talents = ['400126']
        immune_battle = make_wild_battle(self.data.tables, [holy], enemy,
                                         random.Random(62))
        immune = immune_battle.player[0]
        self.assertTrue(immune.immune_all_debuffs)
        self.assertTrue(immune_battle._immune(immune, '2'))
        self.assertTrue(immune_battle._immune(immune, '52'))
        self.assertTrue(immune_battle._immune(immune, '49'))
        divine = generate_pet(self.data.tables, random.Random(63), '100160', 80)
        divine.talents = ['400130']
        resist_battle = make_wild_battle(self.data.tables, [divine], enemy,
                                         random.Random(64))
        resist = resist_battle.player[0]
        self.assertEqual(20, resist.all_debuff_resist)
        self.assertFalse(resist_battle._immune(resist, '2'))

    def test_x_terrain_talent_uses_land_background(self):
        """Ocean Will switches the battle background to the ocean land type."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.start_battle(next(iter(self.data.tables['VillageEnemy'])))
                ui = app.battle_ui
                base = ui.battle_land()
                unit = app.battle.player_active
                unit.pet.talents = ['400213']
                unit._apply_talent_stats()
                self.assertEqual('2', unit.terrain_override)
                self.assertEqual('2', ui.battle_land())
                self.assertNotEqual('2', base)
                self.assertEqual((960, 576), ui.render().size)
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

    def test_every_x_pet_renders(self):
        missing = []
        for species in self.data.tables['Pet']:
            try:
                image = self.data.pet_image(species)
                if image is None:
                    missing.append((species, 'no image'))
            except Exception as error:  # noqa: BLE001 - collect every pet
                missing.append((species, type(error).__name__, str(error)))
        self.assertFalse(missing, missing[:10])

    def test_every_x_armature_loads(self):
        from pathlib import Path
        errors = []
        for export in Path(self.data_dir).rglob('*.ExportJson'):
            name = export.stem
            try:
                self.data.armature_frames(name)
            except Exception as error:  # noqa: BLE001 - collect every armature
                errors.append((name, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_every_x_ui_timeline(self):
        from csb_render import CocosUI
        from pathlib import Path
        ui = CocosUI(self.data)
        errors = []
        for path in Path(self.data_dir, 'assets', 'res', 'UI').glob('*.csb'):
            try:
                layout = ui.layout(path.stem)
                duration = int((layout.get('action') or {}).get('duration') or 0)
                for frame in range(0, duration+1, 20):
                    if ui.render(path.stem, (800, 480), timeline_frame=frame) is None:
                        errors.append((path.stem, frame, 'none'))
            except Exception as error:  # noqa: BLE001 - collect every UI timeline
                errors.append((path.stem, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_every_x_skill_effect_draws(self):
        from PIL import Image
        from battle_effects import BattleEffects
        from pet_factory import generate_pet
        pet = generate_pet(self.data.tables, random.Random(1), '100160', 50)

        class UI:
            pet_bones = {'player': {'p_center': (400, 300), 'p_shadow': (400, 320)},
                         'enemy': {'p_center': (600, 300), 'p_shadow': (600, 320)}}
            pet_positions = {'player': (400, 300), 'enemy': (600, 300)}
            anim = None

            def presentation_unit(self, enemy):
                return type('Unit', (), {'pet': pet})()

        ui = UI()
        effects = BattleEffects(self.data)
        errors = []
        for skill_id in self.data.tables['Skill']:
            plan = effects.plan(skill_id, 'player')
            if not plan:
                continue
            ui.anim = {'effect': plan,
                       'age': plan['hit'] if plan['hit'] is not None else plan['duration']/2,
                       'side': 'player'}
            for rear in (False, True):
                try:
                    frame = Image.new('RGBA', (800, 480))
                    effects.draw(frame, ui, rear)
                except Exception as error:  # noqa: BLE001 - collect every effect
                    errors.append((skill_id, rear, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_every_x_skill_effect_full_timeline(self):
        """Draw each authored effect at start, middle, hit and final frame."""
        from PIL import Image
        from battle_effects import BattleEffects
        from pet_factory import generate_pet
        pet = generate_pet(self.data.tables, random.Random(1), '100160', 50)

        class UI:
            pet_bones = {'player': {'p_center': (400, 300), 'p_shadow': (400, 320)},
                         'enemy': {'p_center': (600, 300), 'p_shadow': (600, 320)}}
            pet_positions = {'player': (400, 300), 'enemy': (600, 300)}
            anim = None

            def presentation_unit(self, enemy):
                return type('Unit', (), {'pet': pet})()

        ui = UI()
        effects = BattleEffects(self.data)
        errors = []
        for skill_id in self.data.tables['Skill']:
            plan = effects.plan(skill_id, 'player')
            if not plan:
                continue
            ages = (0, plan['duration']/2, max(0, plan['duration']-.01),
                    plan['hit'] if plan['hit'] is not None else 0)
            for age in ages:
                ui.anim = {'effect': plan, 'age': age, 'side': 'player'}
                for rear in (False, True):
                    try:
                        effects.draw(Image.new('RGBA', (800, 480)), ui, rear)
                    except Exception as error:  # noqa: BLE001 - collect every frame
                        errors.append((skill_id, age, rear, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

    def test_every_x_skill_effect_plan_and_face(self):
        from battle_effects import BattleEffects
        effects = BattleEffects(self.data)
        missing = []
        for skill_id in self.data.tables['Skill']:
            try:
                effects.plan(skill_id, 'player')
            except Exception as error:  # noqa: BLE001 - collect every skill
                missing.append((skill_id, type(error).__name__, str(error)))
        self.assertFalse(missing, missing[:10])
        # The only missing authored effect asset in this APK is 突袭 (133_tuxi).
        for row_id in ('3209',):
            row = self.data.tables['SkillEffect'].get(row_id, {})
            self.assertEqual(row.get('path1'), '133_tuxi')
        for face in range(1, 9):
            self.assertIsNotNone(self.data.armature('face', str(face), 10), face)

    def test_every_x_skill_executes_in_battle(self):
        from battle import Battle
        from pet_factory import generate_pet
        errors = []
        for skill in self.data.tables['Skill']:
            try:
                player = generate_pet(self.data.tables, random.Random(1), '100160', 200)
                player.skills = [skill]
                enemy = generate_pet(self.data.tables, random.Random(2), '100160', 200)
                battle = Battle(self.data.tables, [player], [enemy],
                                random.Random(3), kind='trainer', name='skill')
                battle.player[0].energy = battle.player[0].max_energy = 9999
                battle.choose_skill(0)
            except Exception as error:  # noqa: BLE001 - collect every skill
                errors.append((skill, type(error).__name__, str(error)))
        self.assertFalse(errors, errors[:10])

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

    def test_x_battle_start_effect_survives_first_tick(self):
        """A long frame that created the battle must not skip the intro."""
        from types import SimpleNamespace
        from battle_ui import BattleUI
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                unit = SimpleNamespace(side='player', hp=10, alive=True,
                                       pet=SimpleNamespace(uid=1, species='100001'))
                enemy = SimpleNamespace(side='enemy', hp=10, alive=True,
                                        pet=SimpleNamespace(uid=2, species='100001'))
                battle = SimpleNamespace(player=[unit], enemy=[enemy], events=[],
                                         result=None, kind='wild',
                                         player_active=unit, enemy_active=enemy)
                ui = BattleUI(app, battle, opening=True)
                transition = ui.opening_transition
                self.assertGreater(transition, 0)
                # PetController uses Skill/chuchongguang for the appearance
                # flash; vfx_appear is a skill asset and must not stand in.
                self.assertIsNotNone(
                    self.data.armature('chuchongguang', 'Animation1', 0))
                ui.advance(seconds=10)
                self.assertIsNotNone(ui.opening_frame)
                self.assertLess(ui.opening_frame, transition)
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

    def test_x_battle_start_uses_original_ball(self):
        """PetController's kaichong Animation4 ball must open at battle start."""
        from types import SimpleNamespace
        from battle_ui import BattleUI
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                from battle import make_wild_battle
                import random
                app = NativeGame(root, self.data)
                battle = make_wild_battle(
                    self.data.tables, app.state.pets,
                    next(iter(self.data.tables['VillageEnemy'])), random.Random(1))
                battle.kind = 'wild'
                ui = BattleUI(app, battle, opening=True)
                transition = ui.opening_transition
                self.assertIsNotNone(
                    self.data.armature('kaichong', 'Animation4', 0))
                self.assertEqual(('player',), ui._entry_ball_sides())
                ui.opening_frame = transition+10
                ui.frame, ui._signature = None, None
                self.assertIsNotNone(ui.render())
                ui.opening_frame = transition+30
                ui.frame, ui._signature = None, None
                self.assertIsNotNone(ui.render())
                self.assertIsNotNone(ui.opening_frame)
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

    def test_x_zero_sized_effect_frames_are_skipped(self):
        """An empty atlas crop must not divide by a zero sprite dimension."""
        checked = 0
        seen = set()
        for row in self.data.tables['SkillEffect'].values():
            for path in (row.get('path1'), row.get('path2')):
                if not path or path in seen:
                    continue
                seen.add(path)
                frames = self.data.armature_frames(path)
                if not any(im.width <= 0 or im.height <= 0
                           for im in frames.values()):
                    continue
                checked += 1
                for frame in range(120):
                    self.data.armature(path, 'Animation1', frame)
        self.assertGreaterEqual(checked, 2)

    def test_x_battle_status_uses_original_buff_icon(self):
        """SkillState.stateId must select the authored buff_<id>.png badge."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from battle import Buff
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.start_battle(next(iter(self.data.tables['VillageEnemy'])))
                ui = app.battle_ui
                ui.opening_frame = None
                unit = app.battle.player_active
                unit.add_buff('2', Buff('2', 6, '9,15', 2, name='中毒'))
                self.assertEqual((32, 28), ui._buff_icon('2').size)
                ui.frame, ui._signature = None, None
                ui.render()
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

    def test_x_battle_switch_plays_appearance_flash(self):
        """A switched-in pet scales in under the authored chuchongguang."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.start_battle(next(iter(self.data.tables['VillageEnemy'])))
                ui = app.battle_ui
                ui.opening_frame = None
                unit = app.battle.player_active
                ui.anim, ui.anim_queue = None, []
                app.battle.events = [{'type': 'switch', 'side': 'player',
                                      'uid': unit.pet.uid, 'name': unit.name}]
                ui._event_batch, ui._event_cursor = None, 0
                ui._capture_events()
                self.assertEqual('switch', ui.anim['kind'])
                ui.anim['age'] = 6
                ui.frame, ui._signature = None, None
                self.assertEqual((960, 576), ui.render().size)
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

    def test_x_single_enemy_story_fights_allow_capture(self):
        """NpcFight type 1 is the original one-enemy capture battle."""
        import random
        from battle import make_npc_battle
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        wild = make_npc_battle(self.data.tables, state.pets, 90050021,
                               random.Random(1))
        self.assertTrue(wild.can_catch)
        trainer = make_npc_battle(self.data.tables, state.pets, 13110031,
                                  random.Random(1))
        self.assertFalse(trainer.can_catch)

    def test_x_battle_faint_sinks_and_fades(self):
        """A faint event selects the dead pose/fade instead of popping out."""
        from PIL import Image
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.start_battle(next(iter(self.data.tables['VillageEnemy'])))
                ui = app.battle_ui
                ui.opening_frame = None
                enemy = app.battle.enemy_active
                enemy.hp = 0
                ui.anim, ui.anim_queue = None, []
                app.battle.events = [{'type': 'faint', 'side': 'enemy',
                                      'uid': enemy.pet.uid,
                                      'name': enemy.name}]
                ui._event_batch, ui._event_cursor = None, 0
                ui._capture_events()
                self.assertEqual('faint', ui.anim['kind'])
                ui.anim['age'] = 20
                ui.frame, ui._signature = None, None
                self.assertEqual((960, 576), ui.render().size)
                solid = Image.new('RGBA', (2, 2), (255, 255, 255, 255))
                self.assertEqual(0, ui._faint_image(solid, 1.0).getpixel((0, 0))[3])
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

    def test_x_failed_escape_hops_back_to_anchor(self):
        """The failed-escape branch is a 5-point CardinalSplineBy hop."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.start_battle(next(iter(self.data.tables['VillageEnemy'])))
                ui = app.battle_ui
                ui.opening_frame = None
                ui.anim, ui.anim_queue = None, []
                ui.battle.events[:] = [{'type': 'escape_failed', 'rate': 0}]
                ui._event_batch = None
                ui._capture_events()
                self.assertEqual('escape_failed', ui.anim['kind'])
                ui.anim['age'] = 12
                offset, target, _ = ui._animation_offsets()
                self.assertLess(offset[1], 0)
                self.assertEqual((0, 0), target)
                ui.anim['age'] = 24
                self.assertEqual((0, 0), ui._animation_offsets()[0])
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

    def test_x_battle_escape_uses_the_authored_dust(self):
        """particle/escape.plist must actually emit at the fleeing pet."""
        from PIL import Image
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.start_battle(next(iter(self.data.tables['VillageEnemy'])))
                ui = app.battle_ui
                ui.opening_frame = None
                unit = app.battle.player_active
                ui.anim = {'kind': 'escape', 'side': 'player',
                           'target': 'player', 'source_uid': unit.pet.uid,
                           'age': 10, 'duration': 40, 'amount': 0,
                           'crit': False, 'damages': []}
                layer = Image.new('RGBA', (960, 576))
                ui._draw_escape_dust(layer)
                self.assertIsNotNone(layer.getbbox())
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

    def test_x_battle_escape_runs_the_pet_away(self):
        """The player pet must leave its anchor on a successful escape."""
        from types import SimpleNamespace
        from battle_ui import BattleUI
        ui = BattleUI.__new__(BattleUI)
        ui.anim = {'kind': 'escape', 'side': 'player', 'age': 20,
                   'duration': 40}
        player_offset, target_offset, _ = ui._animation_offsets()
        self.assertLess(player_offset[0], -100)
        self.assertLess(player_offset[1], 0)
        self.assertEqual((0, 0), target_offset)
        ui.anim['side'] = 'enemy'
        enemy_offset, player_offset, _ = ui._animation_offsets()
        self.assertGreater(enemy_offset[0], 100)
        self.assertEqual((0, 0), player_offset)

    def test_x_battle_plays_pet_wow_sound(self):
        """A pet with an original wowSound roars during battle entrance."""
        from types import SimpleNamespace
        from battle_ui import BattleUI
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                unit = SimpleNamespace(side='player', hp=10, alive=True,
                                       pet=SimpleNamespace(uid=1, species='100001'))
                enemy = SimpleNamespace(side='enemy', hp=10, alive=True,
                                        pet=SimpleNamespace(uid=2, species='100001'))
                battle = SimpleNamespace(player=[unit], enemy=[enemy], events=[],
                                        result=None, kind='wild',
                                        player_active=unit, enemy_active=enemy)
                ui = BattleUI(app, battle, opening=True)
                played = []
                enemy_played = []
                ui.effect_audio = SimpleNamespace(
                    play=lambda value: played.append(str(value)),
                    effect2=lambda value: enemy_played.append(str(value)))
                for _ in range(20):
                    ui.advance(seconds=1)
                    if ui.opening_frame is None:
                        break
                self.assertIn('2001', played)
                self.assertIn('2001', enemy_played)
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

    def test_x_pet_list_plays_name_voice(self):
        """Selecting a PetListUI row plays its original nameSound."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.state.pets.clear()
                app.state.bank.clear()
                app.state.add_generated_pet('100001', 5)
                app.state.active_pet = 0
                app.pets_ui()
                played = []
                app.audio.effect = lambda value: played.append(str(value))
                app.ui_actions['pet_row_0']()
                self.assertIn('1001', played)
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

    def test_x_battle_pet_scale_uses_original(self):
        """Pet.scale survives the battle target-height resize."""
        from types import SimpleNamespace
        from PIL import Image
        from battle_ui import BattleUI
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                ui = BattleUI(app, SimpleNamespace(player=[], enemy=[], events=[], result=None, kind='wild'))
                heights = {}
                for species in ('100001', '101152'):
                    unit = SimpleNamespace(pet=SimpleNamespace(species=species), alive=True)
                    frame = Image.new('RGBA', (800, 480))
                    ui._pose_cache.clear()
                    ui._draw_pet(frame, unit, (400, 300), 200)
                    cached = next(iter(ui._pose_cache.values()))
                    heights[species] = cached[0].height
                self.assertLess(heights['101152'], heights['100001'])
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

    def test_x_lucky_star_biases_wild_encounters(self):
        """Talent state 31 gives the original Lucky Star rare encounter bias."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.state.pets[0].talents = ['400203']
                app.state.active_pet = 0
                self.assertEqual(5, app.rare_encounter_bonus())
                app.state.rng = random.Random(0)
                picks = [app.pick_wild_enemy(['804001', '804002', '804003'], [1, 1, 1])
                         for _ in range(200)]
                self.assertIn('804003', picks)
                self.assertTrue(set(picks) <= {'804001', '804002', '804003'})
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

    def test_x_super_perfume_uses_function_item(self):
        """The 10x perfume is a FunctionItem and must persist its timer."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.state.inventory['220010'] = 1
                app.use_perfume('220010')
                self.assertEqual(0, app.state.count('220010'))
                perfume = app.state.activities['perfume']
                self.assertEqual('220010', perfume['item'])
                self.assertEqual(300, int(perfume['steps']))
                self.assertTrue(Path(app.save_path).is_file())
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

    def test_x_card_legend_board_ui(self):
        """The recovered CardLegend rules are driven by the original page."""
        from event_runtime import Request
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.state.inventory['220008'] = 1
                app.open_ui(Request('openui', 'card-legend', 1,
                                    {'parameters': {'uiid': 30}}))
                root.update()
                self.assertIn('open_Button', app.ui_actions)
                app.ui_actions['open_Button']()
                root.update()
                self.assertIn('enter_Button', app.ui_actions)
                app.ui_actions['enter_Button']()
                root.update()
                match = app.state.activities.get('cards')
                self.assertIsNotNone(match)
                self.assertEqual(0, app.state.count('220008'))
                for index in range(5):
                    if match.get('result') is not None:
                        break
                    callback = app.ui_action_for(f'our_card_{index}')
                    if callback:
                        callback()
                        root.update()
                self.assertIn(match.get('result'), (-1, 0, 1))
                self.assertEqual('CardLegendResultUI', app.original_page.specs[0][0])
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

    def test_x_capture_ui_animation(self):
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.state.initialize(2)
                key = next(iter(self.data.tables['VillageEnemy']))
                app.start_battle(key)
                root.update()
                ui = app.battle_ui
                ui.advance(seconds=3)
                self.assertIsNone(ui.opening_frame)
                played = []
                ui.effect_audio = SimpleNamespace(play=lambda value: played.append(str(value)))
                app.battle.enemy[0].hp = 1
                app.battle.choose_item('220006')
                ui._after_action()
                self.assertIsNotNone(ui.anim)
                self.assertEqual(ui.anim['kind'], 'capture')
                self.assertEqual(ui.anim['capture_clip'], 'Animation1')
                for _ in range(80):
                    ui.advance(seconds=.05)
                    ui.render()
                    root.update()
                self.assertGreater(ui.result_age, 0)
                self.assertEqual(app.battle.result, 'caught')
                row = self.data.tables['Pet'].get(app.battle.caught_pet.species, {})
                cry = str(row.get('wowSound', '0'))
                if cry not in ('', '0') and cry in self.data.tables.get('Sound', {}):
                    self.assertIn(cry, played)
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

    def test_dot_damage_emits_battle_events(self):
        from battle import Battle, Buff
        from pet_factory import generate_pet
        player = generate_pet(self.data.tables, random.Random(1), '100160', 50)
        enemy = generate_pet(self.data.tables, random.Random(2), '100160', 50)
        battle = Battle(self.data.tables, [player], [enemy],
                        random.Random(3), kind='trainer', name='dot')
        unit = battle.player[0]
        unit.hp = unit.max_hp
        unit.add_buff('2', Buff('2', 2, '2,15', 1, unit.pet.uid, '中毒'))
        battle.events = []
        before = unit.hp
        battle._end_round()
        damage = [event for event in battle.events
                  if event['type'] == 'damage' and event.get('side') == 'player']
        self.assertTrue(damage)
        self.assertEqual(before-damage[0]['amount'], unit.hp)
        self.assertEqual('poison', damage[0]['source'])

    def test_story_speed_achievements(self):
        from achievements import Achievements
        state = self.state
        state.activities['play_seconds'] = 1000
        state.main_task, state.main_state = 260, 4
        self.assertTrue(state.submit_task(260))
        self.assertEqual(5, state.main_state)
        self.assertEqual(1000, state.activities['story_completed_seconds'])
        achievements = Achievements(state)
        # 3201 allows 50 game hours, 3301 allows 20.
        self.assertEqual((1, 1), achievements.progress('3201')[:2])
        self.assertEqual((1, 1), achievements.progress('3301')[:2])
        state.activities['story_completed_seconds'] = 1300*60
        self.assertEqual((1, 1), achievements.progress('3201')[:2])
        self.assertEqual((0, 1), achievements.progress('3301')[:2])
        state.activities['story_completed_seconds'] = 3100*60
        self.assertEqual((0, 1), achievements.progress('3201')[:2])
        self.assertEqual((0, 1), achievements.progress('3301')[:2])

    def test_battle_levelup_queue_advances(self):
        from types import SimpleNamespace
        from battle_ui import BattleUI
        battle = SimpleNamespace(exp_gained=[
            ('皮卡丘', 100, [10, 11]),
            ('火绒犬', 80, [20]),
        ], drops=[], result='win', caught_pet=None)
        fake = SimpleNamespace(battle=battle, levelup_entries=None,
                               levelup_index=0, levelup_age=0.0)
        fake._levelup_data = lambda: BattleUI._levelup_data(fake)
        self.assertEqual(len(BattleUI._levelup_data(fake)), 2)
        self.assertTrue(BattleUI._levelup_active(fake))
        fake.levelup_index = 1
        self.assertTrue(BattleUI._levelup_active(fake))
        fake.levelup_index = 2
        self.assertFalse(BattleUI._levelup_active(fake))

    def test_battle_levelup_panel_renders(self):
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.start_battle(next(iter(self.data.tables['VillageEnemy'])))
                ui = app.battle_ui
                # This check is about the settlement panel, not the authored
                # battle-start timeline; skip that timeline explicitly.
                ui.opening_frame = None
                ui.advance(seconds=10)
                self.assertIsNone(ui.opening_frame)
                unit = app.battle.player_active
                level = unit.pet.level
                app.battle.result = 'win'
                app.battle.exp_gained = [(unit.name, 120, [level+1])]
                ui.levelup_entries = None
                frame = ui.render()
                self.assertEqual(frame.size, (960, 576))
                self.assertTrue(ui._levelup_active())
                entry = ui._levelup_data()[0]
                rows = ui._levelup_stats(entry, unit)
                self.assertEqual(5, len(rows))
                self.assertTrue(all(row[2] >= 0 for row in rows))
                self.assertIn('result_continue', ui.hits)
                ui.advance(seconds=.1)
                ui.render()
                rect = ui.hits['result_continue']
                # Must be the authored PetLevelUpUI confirm button, not the
                # bottom-right fallback left behind by the stat-row renders.
                self.assertLess(rect[2], 900)
                self.assertLess(rect[3], 560)
                ui.click((rect[0]+rect[2])//2, (rect[1]+rect[3])//2)
                self.assertFalse(ui._levelup_active())
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






    def test_x_counter_reflects_full_damage_and_petrifies(self):
        """State 29 石化反击 returns the full hit and petrifies the attacker."""
        pet = generate_pet(self.data.tables, random.Random(83), '100160', 60)
        battle = make_npc_battle(self.data.tables, [pet], '6208041', random.Random(84))
        attacker, defender = battle.player_active, battle.enemy_active
        attacker.hp, defender.hp = attacker.max_hp, defender.max_hp
        defender.add_buff('29', Buff('29', 2, '28,1', 2, name='石化反击'))
        before = attacker.hp
        self.assertEqual(100, defender.take_damage(100, source=attacker))
        self.assertEqual(100, before-attacker.hp)
        self.assertTrue(attacker.has_state('7'))

    def test_x_free_pet_keeps_one_living_pet(self):
        """cantFreeLastPet guards the last living pet, not only the active one."""
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        first, second = state.pets[0], state.pets[1]
        self.assertTrue(state.can_free_pet(first.uid)[0])
        before = state.count('700001')
        expected = 300*int(self.data.tables['Pet'][first.species]['starLevel'])
        self.assertEqual(expected, state.release_pet(first.uid))
        self.assertNotIn(first, state.pets)
        self.assertEqual(before+expected, state.count('700001'))
        allowed, reason = state.can_free_pet(second.uid)
        self.assertFalse(allowed)
        self.assertEqual('cantFreeLastPet', reason)
        second.hp = 0
        self.assertTrue(state.can_free_pet(second.uid)[0])

    def test_x_variant_pet_unlocks_authored_ride(self):
        """Every Pet row with a rideId must unlock its authored mount."""
        variants = [(key, int(row['rideId'])) for key, row in self.data.tables['Pet'].items()
                    if int(row.get('rideId', 0) or 0)]
        self.assertTrue(variants)
        for species, ride_id in variants:
            self.state.record_pet(species)
            self.assertIn(ride_id, self.state.rides, species)
        self.assertIn(500001, self.state.rides)
        self.assertIn(500007, self.state.rides)

    def test_x_nightmare_sleeps_awake_target_and_drains_sleeper(self):
        """State 31 torments sleepers and puts awake targets to sleep."""
        pet = generate_pet(self.data.tables, random.Random(61), '100160', 80)
        battle = make_wild_battle(self.data.tables, [pet],
                                  next(iter(self.data.tables['VillageEnemy'])),
                                  random.Random(62))
        player, enemy = battle.player[0], battle.enemy[0]
        state = self.data.tables['SkillState']['31']
        enemy.hp, enemy.energy = enemy.max_hp, enemy.max_energy
        battle._apply_state(player, enemy, '31', state)
        self.assertTrue(enemy.has('sleep'))
        self.assertFalse(enemy.has('nightmare'))
        battle._apply_state(player, enemy, '31', state)
        self.assertTrue(enemy.has('nightmare'))
        hp, energy = enemy.hp, enemy.energy
        battle._end_round()
        self.assertLess(enemy.hp, hp)
        self.assertLess(enemy.energy, energy)
        enemy.buffs = [buff for buff in enemy.buffs if buff.key != '5']
        hp, energy = enemy.hp, enemy.energy
        battle._end_round()
        self.assertFalse(enemy.has('nightmare'))
        self.assertEqual(enemy.hp, hp)
        self.assertEqual(enemy.energy, energy)

    def test_x_unmounted_player_keeps_a_visible_body(self):
        """2.10.9 has no role*.ExportJson; the unmounted hero must not vanish."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.state.ride = 0
                app.state.trial_ride = 0
                app.state.sprite_id = '10001'
                app.player_sprite = '10001'
                self.assertIsNone(self.data.village_sprite('10001'))
                body = app.player_image('standdown')
                self.assertIsNotNone(body)
                self.assertGreater(body.width, 0)
                self.assertGreater(body.height, 0)
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

    def test_x_ambient_air_talk_reaches_its_bubble(self):
        """The authored talk<id> line must become bubble text, not stay unused."""
        from event_runtime import Request
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                authored = Request('airtalk', 'x', 0,
                                   {'parameters': [{'spriteid': 650104, 'index': 0}]})
                self.assertEqual(['忠诚……'], app.air_talk_lines(authored))
                silent = Request('airtalk', 'x', 0,
                                 {'parameters': [{'spriteid': 590902, 'index': 0}]})
                self.assertEqual([], app.air_talk_lines(silent))
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

    def test_x_gathering_raises_battle_experience(self):
        """Skill 300010 state 8 doubles experience for the rest of the battle."""
        pet = generate_pet(self.data.tables, random.Random(89), '100160', 60)
        battle = make_npc_battle(self.data.tables, [pet], '6208041', random.Random(90))
        caster, target = battle.player_active, battle.enemy_active
        caster.exp_multiplier = 1.0
        target.exp_multiplier = 1.0
        battle._apply_states(caster, target, self.data.tables['Skill']['300010'])
        self.assertEqual(2.0, caster.exp_multiplier)
        self.assertEqual(1.0, target.exp_multiplier)
        self.assertTrue(caster.has_state('8'))
        # Re-applying 不叠加 keeps the same bonus.
        battle._apply_states(caster, target, self.data.tables['Skill']['300010'])
        self.assertEqual(2.0, caster.exp_multiplier)

    def test_x_fang_and_equalize_use_original_current_hp(self):
        """愤怒门牙 cuts 25% current HP; 平等 copies the caster's HP."""
        pet = generate_pet(self.data.tables, random.Random(87), '100160', 60)
        battle = make_npc_battle(self.data.tables, [pet], '6208041', random.Random(88))
        battle.rng = SimpleNamespace(randrange=lambda n: 0, random=lambda: .5,
                                     randint=lambda a, b: a, choice=lambda seq: seq[0])
        caster, target = battle.player_active, battle.enemy_active
        target.hp = 400
        battle._apply_states(caster, target, self.data.tables['Skill']['300044'])
        self.assertEqual(300, target.hp)
        caster.hp = 500
        target.hp = 100
        battle._apply_states(caster, target, self.data.tables['Skill']['300055'])
        self.assertEqual(500, target.hp)

    def test_x_counter_petrify_respects_immunity(self):
        """A petrify-immune attacker still takes counter damage but no state."""
        pet = generate_pet(self.data.tables, random.Random(85), '100160', 60)
        battle = make_npc_battle(self.data.tables, [pet], '6208041', random.Random(86))
        attacker, defender = battle.player_active, battle.enemy_active
        attacker.hp, defender.hp = attacker.max_hp, defender.max_hp
        attacker.talent_immune.add('7')
        defender.add_buff('29', Buff('29', 2, '28,1', 2, name='石化反击'))
        before = attacker.hp
        defender.take_damage(80, source=attacker)
        self.assertEqual(80, before-attacker.hp)
        self.assertFalse(attacker.has_state('7'))

    def test_x_mimic_copies_last_enemy_skill(self):
        """Skill 300053 (state 18) copies the opponent's last used skill."""
        pet = generate_pet(self.data.tables, random.Random(81), '100160', 60)
        battle = make_npc_battle(self.data.tables, [pet], '6208041', random.Random(82))
        battle.rng = SimpleNamespace(randrange=lambda n: 0, random=lambda: .5,
                                     randint=lambda a, b: a, choice=lambda seq: seq[0])
        player, enemy = battle.player_active, battle.enemy_active
        enemy.last_skill = '300232'
        battle._apply_states(player, enemy, self.data.tables['Skill']['300053'])
        self.assertEqual('300232', player.mimicked_skill)
        self.assertTrue(player.has('mimic'))
        self.assertEqual('300232', battle.available_skills(player)[0]['id'])
        player.energy = player.max_energy
        battle._use_skill(player, enemy, self.data.tables['Skill']['300232'])
        self.assertEqual('', player.mimicked_skill)
        self.assertFalse(player.has('mimic'))

    def test_x_skill_event_plays_skill_sound(self):
        """Skill.sound is played alongside the SkillEffect armature sound."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.state.initialize(2)
                key = next(iter(self.data.tables['VillageEnemy']))
                app.start_battle(key)
                root.update()
                ui = app.battle_ui
                ui.advance(seconds=3)
                played = []
                ui.effect_audio = SimpleNamespace(play=lambda value: played.append(str(value)))
                app.battle.events = [{'type': 'skill', 'side': 'player',
                                      'uid': app.battle.player_active.pet.uid,
                                      'skill_id': '300232', 'name': '大地之怒'}]
                ui._event_batch = None
                ui._event_cursor = 0
                ui._capture_events()
                self.assertIn('4117', played)
                self.assertEqual(1, ui.anim['shake'])
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

    def test_x_pet_item_effect_uses_original_armature(self):
        """PetItem.effectId resolves to its original SkillEffect armature."""
        from battle_effects import BattleEffects
        effects = BattleEffects(self.data)
        plan = effects.plan_effect('3051')
        self.assertIsNotNone(plan)
        self.assertEqual('zhiyushui', plan['path'])
        self.assertTrue(plan['self_target'])
        self.assertGreater(plan['duration'], 0)
        self.assertEqual('3051', plan['skill_id'])

    def test_x_ground_wrath_shakes_battlefield(self):
        """Skill.shake=1 is the authored Ground Wrath battlefield shake."""
        from battle_ui import BattleUI
        row = self.data.tables['Skill']['300232']
        self.assertEqual(1, int(row['shake']))
        self.assertEqual('大地之怒', row['name'])
        ui = BattleUI.__new__(BattleUI)
        ui.anim = {'shake': 1, 'hit_at': 4, 'age': 6, 'duration': 20}
        x, y = ui._shake_offset()
        self.assertTrue(x or y)
        ui.anim['age'] = 40
        self.assertEqual((0, 0), ui._shake_offset())
        ui.anim = {'shake': 0, 'hit_at': 4, 'age': 6}
        self.assertEqual((0, 0), ui._shake_offset())

    def test_x_battle_item_uses_original_sound(self):
        """PetItem.soundId is the authored battle item sound."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                app.state.initialize(2)
                key = next(iter(self.data.tables['VillageEnemy']))
                app.start_battle(key)
                root.update()
                ui = app.battle_ui
                ui.advance(seconds=3)
                played = []
                ui.effect_audio = SimpleNamespace(play=lambda value: played.append(str(value)))
                unit = app.battle.player_active
                unit.hp = max(1, unit.max_hp-10)
                app.battle.choose_item('230007')
                ui._after_action()
                self.assertIn('4057', played)
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

    def test_x_enemy_item_ai_uses_hp_bands(self):
        """NpcFight.targetHp/useItemRate select enemy heal and cleanse bands."""
        pet = generate_pet(self.data.tables, random.Random(71), '100160', 50)
        battle = make_npc_battle(self.data.tables, [pet], '6208041', random.Random(72))
        enemy = battle.enemy_active
        self.assertIsNone(battle._enemy_item_action())  # never waste at full HP
        enemy.hp = max(1, int(enemy.max_hp*.15))
        battle.rng = SimpleNamespace(randrange=lambda n: 0)
        self.assertEqual('230007', battle._enemy_item_action())
        enemy.hp = max(1, int(enemy.max_hp*.40))
        enemy.buffs = [Buff('2', 3, '0', 0)]
        rolls = iter([80, 0])
        battle.rng = SimpleNamespace(randrange=lambda n: next(rolls))
        self.assertEqual('230009', battle._enemy_item_action())

    def test_x_wild_escape_uses_enemy_life_thresholds(self):
        """VillageEnemy.escapeLife/escapePro are the wild enemy's flee odds."""
        key = next(k for k, r in self.data.tables['VillageEnemy'].items()
                   if len(str(r.get('escapeLife', '')).split(',')) >= 4
                   and len(str(r.get('escapePro', '')).split(',')) >= 4)
        player = generate_pet(self.data.tables, random.Random(3), '100160', 50)
        battle = make_wild_battle(self.data.tables, [player], key, random.Random(4))
        enemy = battle.enemy_active
        enemy.hp = enemy.max_hp
        self.assertEqual(0, battle._enemy_escape_chance())
        enemy.hp = max(1, int(enemy.max_hp*.40))
        self.assertEqual(1, battle._enemy_escape_chance())
        enemy.hp = max(1, int(enemy.max_hp*.20))
        self.assertEqual(3, battle._enemy_escape_chance())
        enemy.hp = max(1, int(enemy.max_hp*.05))
        self.assertEqual(5, battle._enemy_escape_chance())
        battle.rng = SimpleNamespace(randrange=lambda n: 0)
        action = battle._enemy_action()
        self.assertEqual('skip', action['type'])
        self.assertEqual('enemy_escape', battle.result)
        self.assertTrue(enemy.fled)

        # Talent 400205 (state 33) is Affinity Angel: enemies cannot flee.
        player2 = generate_pet(self.data.tables, random.Random(5), '100160', 50)
        player2.talents = ['400205']
        battle2 = make_wild_battle(self.data.tables, [player2], key, random.Random(6))
        battle2.player_active._apply_talent_stats()
        battle2.enemy_active.hp = max(1, int(battle2.enemy_active.max_hp*.05))
        self.assertTrue(battle2.player_active.enemy_cannot_escape)
        self.assertEqual(0, battle2._enemy_escape_chance())

    def test_x_wild_capture_reaches_caught(self):
        pets = [generate_pet(self.data.tables, random.Random(22), '100160', 80)
                for _ in range(2)]
        key = next(iter(self.data.tables['VillageEnemy']))
        battle = make_wild_battle(self.data.tables, pets, key, random.Random(23))
        battle.enemy[0].hp = 1
        event_types = [event['type'] for event in battle.choose_item('220006')]
        self.assertEqual(battle.result, 'caught')
        self.assertIn('catch_attempt', event_types)
        self.assertIn('caught', event_types)
        self.assertIsNotNone(battle.caught_pet)

    def test_every_x_trigger_target_exists(self):
        triggers = self.data.event('pEventContents.json')
        files = {path.name for path in (self.data.root/'events').glob('pEvent*.json')}
        missing_scripts = [t.get('id') for t in triggers
                           if f"pEvent{t.get('id')}.json" not in files]
        self.assertFalse(missing_scripts, missing_scripts[:10])
        names = set(self.data.tables['Npc'])
        for key in self.data.tables['VillageMap']:
            world = self.data.load_map(key)
            for obj in world.objects:
                names.add(str(obj.get('name', '')))
                for field in ('area', 'npcId', 'npcid'):
                    if obj.get('props', {}).get(field) is not None:
                        names.add(str(obj['props'][field]))
        missing = []
        for trigger in triggers:
            condition = trigger.get('conditions_add') or {}
            for field in ('area', 'npcid'):
                value = condition.get(field)
                if value is not None and str(value) not in names:
                    missing.append((trigger.get('id'), field, value))
        self.assertFalse(missing, missing[:20])

    def test_x_morpheus_map_and_triggers(self):
        row = self.data.tables['VillageMap']['1501']
        self.assertEqual(row['fileName'], 'map1501.tmx')
        self.assertEqual(row['name'], '墨菲斯')
        self.assertTrue({'150101', '150102', '150103', '150117'} <= set(row['exitIds'].split(',')))
        world = self.data.load_map(1501)
        names = {str(obj.get('name')) for obj in world.objects}
        self.assertTrue({'150101', '150102', '150103', '150134'} <= names)
        triggers = self.data.event('pEventContents.json')
        self.assertTrue(any(str(t.get('id')) in ('1501006', '1501009', '1501010', '1501011')
                            for t in triggers))

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

    def test_x_moria_guardian_reaches_next_task(self):
        """The missed-arrival fix must play the whole 5205001 scene and submit 115."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 115, 3
                app.state.events['5202001'] = 1
                app.load_map(5205)
                app.request_map('520501')
                battle = None
                for _ in range(6000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                     'tapscreen', 'button'):
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
                self.assertEqual(115, app.state.main_task)
                battle.result = 'win'
                app.finish_battle()
                for _ in range(6000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                     'tapscreen', 'button'):
                        app.interact()
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.ui_open:
                        app.close_ui('yes')
                    elif (app.runtime.running and not app.battle and not request
                          and not app.pending_wait):
                        app.drive()
                    elif not app.runtime.running and not request:
                        break
                self.assertFalse(app.runtime.running)
                self.assertEqual(116, app.state.main_task)
                self.assertEqual(1, app.state.events.get('5205001', 0))
                self.assertEqual(1, app.state.inventory.get('270080', 0))
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

    def test_x_olympia_council_reaches_task_117(self):
        """Task 116's gym council is an arrival cutscene, not a talk prompt."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 116, 3
                app.state.events['5205001'] = 1
                app.load_map(6501)
                app.request_map('650101')
                self.assertEqual('pEvent6501007.json', app.runtime.file)
                seen = set()
                for _ in range(12000):
                    root.update()
                    time.sleep(.001)
                    if app.dialogue:
                        seen.add(app.dialogue)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                     'tapscreen', 'button'):
                        app.interact()
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.ui_open:
                        app.close_ui('yes')
                    elif (app.runtime.running and not request and not app.pending_wait
                          and not app.battle):
                        app.drive()
                    elif not app.runtime.running and not request:
                        break
                self.assertFalse(app.runtime.running)
                self.assertEqual(305, app.map_id)
                self.assertEqual(117, app.state.main_task)
                self.assertEqual(1, app.state.events.get('6501007', 0))
                self.assertIn('忠诚……', seen)
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

    def test_x_sea_return_chain_reaches_task_118(self):
        """703002 -> gym 6501008 -> 1101001 must submit 117 and land on 1101."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 117, 3
                app.state.events['6501007'] = 1
                app.load_map(6501)
                app.request_map('70301')
                self.assertEqual('pEvent703002.json', app.runtime.file)
                for _ in range(15000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                     'tapscreen', 'button'):
                        app.interact()
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.ui_open:
                        app.close_ui('yes')
                    elif (app.runtime.running and not request and not app.pending_wait
                          and not app.battle):
                        app.drive()
                    elif not app.runtime.running and not request:
                        break
                self.assertFalse(app.runtime.running)
                self.assertEqual(1101, app.map_id)
                self.assertEqual(118, app.state.main_task)
                self.assertEqual(1, app.state.events.get('703002', 0))
                self.assertEqual(1, app.state.events.get('6501008', 0))
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

    def test_x_final_kings_shield_reaches_task_120(self):
        """The third shield's area scene must submit 119 and reach 5708."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 119, 4
                for key in ('5703001', '5704902', '5705903', '5706903'):
                    app.state.events[key] = 1
                app.load_map(5707)
                app.play_event('pEvent5707001.json')
                battle = None
                for _ in range(12000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                     'tapscreen', 'button'):
                        app.interact()
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.battle:
                        battle = app.battle
                        break
                    elif not app.runtime.running and not request:
                        break
                self.assertIsNotNone(battle, app.event_issue)
                battle.result = 'win'
                app.finish_battle()
                for _ in range(15000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                     'tapscreen', 'button'):
                        app.interact()
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.ui_open:
                        app.close_ui('yes')
                    elif (app.runtime.running and not request and not app.pending_wait
                          and not app.battle):
                        app.drive()
                    elif not app.runtime.running and not request:
                        break
                self.assertFalse(app.runtime.running)
                self.assertEqual(5708, app.map_id)
                self.assertEqual(120, app.state.main_task)
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

    def test_x_buede_trials_reach_task_127(self):
        """124 -> the two disciples -> Buede -> material errands (task 127)."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 124, 3
                app.state.events['602013'] = 1

                def play():
                    for _ in range(30000):
                        root.update()
                        time.sleep(.001)
                        request = app.display_request
                        if request:
                            app.interact()
                        elif app.pending_wait:
                            app.pending_wait = None
                            app.runtime.resume()
                            app.drive()
                        elif app.battle:
                            app.battle.result = 'win'
                            app.finish_battle()
                        elif app.ui_open:
                            app.close_ui('yes')
                        elif app.runtime.running:
                            app.drive()
                        else:
                            return

                app.load_map(5909)
                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '5909001')
                app.runtime.start('pEvent5909001.json', trigger)
                app.drive()
                play()
                self.assertEqual(125, app.state.main_task)
                self.assertFalse(app.runtime.running, app.event_issue)

                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '5909002')
                app.runtime.start('pEvent5909002.json', trigger)
                app.drive()
                play()
                self.assertEqual(126, app.state.main_task)
                self.assertEqual([1, 1], app.state.task_counts['main:125'])
                self.assertEqual(1, app.state.events.get('5909002', 0))
                self.assertEqual(1, app.state.events.get('5909003', 0))

                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '5909004')
                app.runtime.start('pEvent5909004.json', trigger)
                app.drive()
                play()
                self.assertFalse(app.runtime.running, app.event_issue)
                self.assertEqual(109, app.map_id)
                self.assertEqual(127, app.state.main_task)
                self.assertEqual(1, app.state.events.get('5909004', 0))
                self.assertEqual(1, app.state.events.get('109008', 0))
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

    def test_x_wood_errand_starts_task_128(self):
        """305004 takes the blueprint and asks for five route birds."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 127, 3
                app.state.events['109008'] = 1
                app.state.inventory['270083'] = 1
                app.load_map(305)
                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '305004')
                app.runtime.start('pEvent305004.json', trigger)
                app.drive()
                for _ in range(20000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                    'tapscreen', 'button'):
                        app.interact()
                    elif app.ui_open:
                        app.close_ui('yes')
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.runtime.running:
                        app.drive()
                    else:
                        break
                self.assertFalse(app.runtime.running, app.event_issue)
                self.assertEqual(128, app.state.main_task)
                self.assertEqual(1, app.state.events.get('305004', 0))
                self.assertEqual(0, app.state.inventory.get('270083', 0))
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

    def test_x_metal_errand_starts_task_131(self):
        """503004 hands the blueprint to Paul and starts the metal errand."""
        from event_runtime import EventRuntime
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 130, 3
        state.inventory['270084'] = 1
        trigger = {'id': 503004, 'type': 'talk',
                   'conditions_add': {'npcid': 50314},
                   'conditions_mtask': [130, 4],
                   'conditions_event': [305006, 1]}
        runtime = EventRuntime(self.data, state)
        runtime.start('pEvent503004.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume(True if request.kind == 'accepttask' else
                           ([] if request.kind == 'costtaskitem' else None))
        self.assertEqual(131, state.main_task)
        self.assertEqual(3, state.main_state)
        self.assertEqual(1, state.events.get('503004', 0))
        self.assertEqual(0, state.inventory.get('270084', 0))

    def test_x_metal_capture_consumes_five_guardians(self):
        """Five 100093 are consumed by 503005 before the cave trip."""
        from event_runtime import EventRuntime
        from game_state import GameState
        from pet_factory import generate_pet
        from task_progress import TaskProgress
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 131, 3
        state.events['503004'] = 1
        uids = []
        for _ in range(5):
            pet = generate_pet(self.data.tables, state.rng, '100093', 20)
            state.receive_pet(pet)
            uids.append(pet.uid)
        TaskProgress(state).update('catch', '100093')
        self.assertEqual(4, state.main_state)
        trigger = {'id': 503005, 'type': 'talk',
                   'conditions_add': {'npcid': 50314},
                   'conditions_mtask': [131, 3, 131, 4],
                   'conditions_event': [503004, 1]}
        runtime = EventRuntime(self.data, state)
        runtime.start('pEvent503005.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume(True if request.kind == 'accepttask' else
                           (uids if request.kind == 'costtaskitem' else None))
        self.assertEqual(131, state.main_task)
        self.assertEqual(4, state.main_state)
        self.assertEqual(1, state.events.get('503005', 0))
        self.assertEqual([], [p.uid for p in state.pets if p.species == '100093'])
        self.assertEqual(1, len(state.pets))

    def test_x_voyage_arrival_reaches_task_138(self):
        """119016 fires on the 11909 area and starts the unknown-land task."""
        from event_runtime import EventRuntime
        from game_state import GameState
        from task_progress import TaskProgress
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 137, 3
        state.events['119015'] = 1
        runtime = EventRuntime(self.data, state)
        self.assertTrue(runtime.notify('toarea', area=11909))
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume('win' if request.kind == 'fight' else
                           (True if request.kind == 'accepttask' else
                            ([] if request.kind == 'costtaskitem' else None)))
        self.assertEqual(1, state.events.get('119016', 0))
        TaskProgress(state).update('area', 11909)
        # 137 stays ready at state 4 until the 1206001 and 1202001 scenes.
        self.assertEqual(137, state.main_task)
        self.assertEqual(4, state.main_state)
        for map_id, event_id in ((1206, 1206001), (1202, 1202001)):
            self.assertTrue(runtime.notify('tomap', map=map_id))
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else
                               (True if request.kind == 'accepttask' else
                                ([] if request.kind == 'costtaskitem' else None)))
            self.assertEqual(1, state.events.get(str(event_id), 0))
        self.assertEqual(138, state.main_task)
        self.assertEqual(3, state.main_state)

    def test_x_island_festival_reaches_task_140(self):
        """1202002 -> 8052001 -> 1203001 must reach the festival fight."""
        from event_runtime import EventRuntime
        from game_state import GameState
        from task_progress import TaskProgress
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 138, 3
        state.events['1202001'] = 1
        runtime = EventRuntime(self.data, state)

        def play(notification, **parameters):
            self.assertTrue(runtime.notify(notification, **parameters))
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else
                               (True if request.kind == 'accepttask' else
                                ([] if request.kind == 'costtaskitem' else None)))

        play('toarea', area=120201)
        self.assertEqual(1, state.events.get('1202002', 0))
        TaskProgress(state).update('area', 120201)
        self.assertEqual(4, state.main_state)
        play('tomap', map=8052)
        self.assertEqual(1, state.events.get('8052001', 0))
        self.assertEqual(139, state.main_task)
        self.assertEqual(3, state.main_state)
        play('toarea', area=120301)
        self.assertEqual(1, state.events.get('1203001', 0))
        self.assertEqual(140, state.main_task)
        self.assertEqual(3, state.main_state)

    def test_x_island_ritual_battles_reach_task_145(self):
        """The ritual fights and shrine trial must submit 140 through 144."""
        from event_runtime import EventRuntime
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 140, 3
        state.events['1203001'] = 1
        runtime = EventRuntime(self.data, state)
        for event_id, npc, task, next_task in (
                (1203002, 1203091, 140, 141),
                (1203003, 1203092, 141, 142),
                (1203004, 1203093, 142, 143)):
            trigger = {'id': event_id, 'type': 'talk',
                       'conditions_add': {'npcid': 120309},
                       'conditions_mtask': [task, 3]}
            runtime.start(f'pEvent{event_id}.json', trigger)
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else None)
            self.assertEqual(next_task, state.main_task)
            self.assertEqual(3, state.main_state)

        for area, event_id in ((120401, 1204001), (120501, 1205001)):
            self.assertTrue(runtime.notify('toarea', area=area))
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else None)
            self.assertEqual(1, state.events.get(str(event_id), 0))
        self.assertEqual(145, state.main_task)
        self.assertEqual(3, state.main_state)

        trigger = {'id': 1205002, 'type': 'talk',
                   'conditions_add': {'npcid': 120501},
                   'conditions_mtask': [145, 3],
                   'conditions_event': [1205001, 1]}
        runtime.start('pEvent1205002.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            fight = None
            if request.kind == 'fight':
                parameters = request.data.get('parameters', {})
                fight = int(parameters.get('npcid', 0))
            runtime.resume('win' if request.kind == 'fight' else None)
            if fight:
                from task_progress import TaskProgress
                TaskProgress(state).update('fight', 2, 1, fight, -1)
        self.assertEqual(145, state.main_task)
        self.assertEqual(4, state.main_state)
        self.assertEqual(1, state.events.get('1205002'))

        for event_id, map_id, previous in ((1203005, 1203, 1205002),
                                           (1202003, 1202, 1203005)):
            trigger = {'id': event_id, 'type': 'tomap',
                       'conditions_add': {'map': map_id},
                       'conditions_mtask': [145, 4],
                       'conditions_event': [previous, 1]}
            runtime.start(f'pEvent{event_id}.json', trigger)
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else None)
            self.assertEqual(1, state.events.get(str(event_id)))
        self.assertEqual(146, state.main_task)
        self.assertEqual(3, state.main_state)

    def test_x_island_relics_reach_task_155(self):
        """The three island guardians and the center shrine must open 155."""
        from event_runtime import EventRuntime
        from game_state import GameState
        from task_progress import TaskProgress
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 146, 3
        state.events['1202003'] = 1
        runtime = EventRuntime(self.data, state)

        def run(event_id, trigger):
            runtime.start(f'pEvent{event_id}.json', trigger)
            while True:
                request = runtime.next()
                if request is None:
                    break
                fight = None
                if request.kind == 'fight':
                    fight = int(request.data.get('parameters', {}).get('npcid', 0))
                runtime.resume('win' if request.kind == 'fight' else None)
                if fight:
                    TaskProgress(state).update('fight', 2, 1, fight, -1)

        run(1301001, {'id': 1301001, 'type': 'tomap',
                      'conditions_add': {'map': 1301},
                      'conditions_mtask': [146, 3],
                      'conditions_event': [1202003, 1]})
        self.assertEqual(147, state.main_task)
        for event_id, previous, kind, value, task, npc, next_task in (
                (1305001, 1301001, 'toarea', 130501, 147, 0, 148),
                (1305002, 1305001, 'talk', 0, 148, 130501, 149),
                (1306001, 1305002, 'toarea', 130601, 149, 0, 150),
                (1306002, 1306001, 'talk', 0, 150, 130601, 151),
                (1307001, 1306002, 'toarea', 130701, 151, 0, 152),
                (1307002, 1307001, 'talk', 0, 152, 130701, 153),
                (1308001, 1307002, 'toarea', 130801, 153, 0, 154),
                (1308002, 1308001, 'talk', 0, 154, 130801, 155)):
            trigger = {'id': event_id, 'type': kind,
                       'conditions_mtask': [task, 3],
                       'conditions_event': [previous, 1]}
            if kind == 'toarea':
                trigger['conditions_add'] = {'area': value}
            else:
                trigger['conditions_add'] = {'npcid': npc}
            run(event_id, trigger)
            if event_id == 1308002:
                self.assertEqual(154, state.main_task)
                self.assertEqual(4, state.main_state)
            else:
                self.assertEqual(next_task, state.main_task)
                self.assertEqual(3, state.main_state)

        run(1301002, {'id': 1301002, 'type': 'tomap',
                      'conditions_add': {'map': 1301},
                      'conditions_mtask': [154, 4],
                      'conditions_event': [1308002, 1]})
        self.assertEqual(155, state.main_task)
        self.assertEqual(3, state.main_state)

    def test_x_phantom_island_reaches_task_162(self):
        """155 -> 161 must play the phantom island, captain and forest chain."""
        from event_runtime import EventRuntime
        from game_state import GameState
        from task_progress import TaskProgress
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 155, 3
        state.events['1301002'] = 1
        runtime = EventRuntime(self.data, state)

        def play(event_id, trigger, update=None):
            runtime.start(f'pEvent{event_id}.json', trigger)
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else None)
            if update:
                TaskProgress(state).update(*update)

        play(1501001, {'id': 1501001, 'type': 'toarea',
                       'conditions_add': {'area': 130101},
                       'conditions_mtask': [155, 3],
                       'conditions_event': [1301002, 1]},
             ('area', 130101))
        play(1501002, {'id': 1501002, 'type': 'tomap',
                       'conditions_add': {'map': 1309},
                       'conditions_mtask': [155, 4],
                       'conditions_event': [1501001, 1]},
             ('map', 1309))
        self.assertEqual(156, state.main_task)
        play(1501003, {'id': 1501003, 'type': 'toarea',
                       'conditions_add': {'area': 131101},
                       'conditions_mtask': [156, 3],
                       'conditions_event': [1501002, 1]},
             ('area', 131101))
        self.assertEqual(157, state.main_task)
        play(1501004, {'id': 1501004, 'type': 'toarea',
                       'conditions_add': {'area': 131102},
                       'conditions_mtask': [157, 3],
                       'conditions_event': [1501003, 1]},
             ('area', 131102))
        self.assertEqual(158, state.main_task)
        play(1311001, {'id': 1311001, 'type': 'talk',
                       'conditions_add': {'npcid': 131104},
                       'conditions_mtask': [158, 4],
                       'conditions_event': [1501004, 1]})
        self.assertEqual(159, state.main_task)
        play(1312001, {'id': 1312001, 'type': 'toarea',
                       'conditions_add': {'area': 131204},
                       'conditions_mtask': [159, 3],
                       'conditions_event': [1311001, 1]},
             ('area', 131204))
        self.assertEqual(160, state.main_task)
        play(1311002, {'id': 1311002, 'type': 'toarea',
                       'conditions_add': {'area': 131103},
                       'conditions_mtask': [160, 3],
                       'conditions_event': [1312001, 1]},
             ('area', 131103))
        self.assertEqual(161, state.main_task)
        play(1311003, {'id': 1311003, 'type': 'toarea',
                       'conditions_add': {'area': 131104},
                       'conditions_mtask': [161, 3],
                       'conditions_event': [1311002, 1]},
             ('area', 131104))
        play(1311004, {'id': 1311004, 'type': 'tomap',
                       'conditions_add': {'map': 1402},
                       'conditions_mtask': [161, 4],
                       'conditions_event': [1311003, 1]},
             ('map', 1402))
        play(1311005, {'id': 1311005, 'type': 'tomap',
                       'conditions_add': {'map': 9004},
                       'conditions_mtask': [161, 4],
                       'conditions_event': [1311004, 1]},
             ('map', 9004))
        self.assertEqual(162, state.main_task)
        self.assertEqual(3, state.main_state)

    def test_x_phantom_shrine_reaches_task_171(self):
        """162 -> 170 must include the capture, shrine battle and legend."""
        from event_runtime import EventRuntime
        from game_state import GameState
        from task_progress import TaskProgress
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 162, 3
        state.events['1311005'] = 1
        runtime = EventRuntime(self.data, state)

        def play(event_id, trigger, update=None):
            runtime.start(f'pEvent{event_id}.json', trigger)
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else None)
            if update:
                TaskProgress(state).update(*update)

        play(9005001, {'id': 9005001, 'type': 'tomap',
                       'conditions_add': {'map': 9005},
                       'conditions_mtask': [162, 3],
                       'conditions_event': [1311005, 1]},
             ('map', 9005))
        self.assertEqual(163, state.main_task)
        self.assertEqual(4, state.main_state)
        play(9005002, {'id': 9005002, 'type': 'talk',
                       'conditions_add': {'npcid': 900502},
                       'conditions_mtask': [163, 4],
                       'conditions_event': [9005001, 1]})
        self.assertEqual(164, state.main_task)
        play(1312002, {'id': 1312002, 'type': 'tomap',
                       'conditions_add': {'map': 1312},
                       'conditions_mtask': [164, 3],
                       'conditions_event': [9005002, 1]},
             ('map', 1312))
        self.assertEqual(165, state.main_task)
        play(1313001, {'id': 1313001, 'type': 'toarea',
                       'conditions_add': {'area': 131301},
                       'conditions_mtask': [165, 3],
                       'conditions_event': [1312002, 1]},
             ('area', 131301))
        self.assertEqual(166, state.main_task)
        play(9003001, {'id': 9003001, 'type': 'toarea',
                       'conditions_add': {'area': 900301},
                       'conditions_mtask': [166, 3],
                       'conditions_event': [1313001, 1]},
             ('area', 900301))
        self.assertEqual(167, state.main_task)
        play(9003002, {'id': 9003002, 'type': 'talk',
                       'conditions_add': {'npcid': 900304},
                       'conditions_mtask': [167, 4],
                       'conditions_event': [9003001, 1]})
        play(9003003, {'id': 9003003, 'type': 'tomap',
                       'conditions_add': {'map': 1311},
                       'conditions_mtask': [167, 4],
                       'conditions_event': [9003002, 1]},
             ('map', 1311))
        self.assertEqual(168, state.main_task)
        play(1403001, {'id': 1403001, 'type': 'toarea',
                       'conditions_add': {'area': 140302},
                       'conditions_mtask': [168, 3],
                       'conditions_event': [9003003, 1]},
             ('area', 140302))
        self.assertEqual(169, state.main_task)
        play(9008001, {'id': 9008001, 'type': 'toarea',
                       'conditions_add': {'area': 900801},
                       'conditions_mtask': [169, 3],
                       'conditions_event': [1403001, 1]},
             ('area', 900801))
        play(9008002, {'id': 9008002, 'type': 'toarea',
                       'conditions_add': {'area': 900802},
                       'conditions_mtask': [169, 3],
                       'conditions_event': [9008001, 1]},
             ('area', 900802))
        self.assertEqual(170, state.main_task)
        play(1404001, {'id': 1404001, 'type': 'toarea',
                       'conditions_add': {'area': 140401},
                       'conditions_mtask': [170, 3],
                       'conditions_event': [9008002, 1]},
             ('area', 140401))
        play(1404002, {'id': 1404002, 'type': 'tomap',
                       'conditions_add': {'map': 1402},
                       'conditions_mtask': [170, 4],
                       'conditions_event': [1404001, 1]},
             ('map', 1402))
        self.assertEqual(171, state.main_task)
        self.assertEqual(3, state.main_state)

    def test_x_morphis_island_reaches_task_182(self):
        """171 -> 181 must play Morphis, the highland gate and the license."""
        from event_runtime import EventRuntime
        from game_state import GameState
        from task_progress import TaskProgress
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 171, 3
        state.events['1404002'] = 1
        runtime = EventRuntime(self.data, state)

        def play(event_id, trigger, update=None):
            runtime.start(f'pEvent{event_id}.json', trigger)
            while True:
                request = runtime.next()
                if request is None:
                    break
                runtime.resume('win' if request.kind == 'fight' else None)
            if update:
                TaskProgress(state).update(*update)

        play(1501006, {'id': 1501006, 'type': 'toarea',
                       'conditions_add': {'area': 150101},
                       'conditions_mtask': [171, 3],
                       'conditions_event': [1404002, 1]},
             ('area', 150101))
        self.assertEqual(172, state.main_task)
        play(1501007, {'id': 1501007, 'type': 'toarea',
                       'conditions_add': {'area': 685501},
                       'conditions_mtask': [172, 3],
                       'conditions_event': [1501006, 1]},
             ('area', 685501))
        self.assertEqual(173, state.main_task)
        play(1501008, {'id': 1501008, 'type': 'tomap',
                       'conditions_add': {'map': 1501},
                       'conditions_mtask': [173, 3],
                       'conditions_event': [1501007, 1]},
             ('map', 1501))
        self.assertEqual(174, state.main_task)
        play(1501009, {'id': 1501009, 'type': 'talk',
                       'conditions_add': {'npcid': 150134},
                       'conditions_mtask': [174, 4],
                       'conditions_event': [1501008, 1]})
        self.assertEqual(175, state.main_task)
        play(1502001, {'id': 1502001, 'type': 'toarea',
                       'conditions_add': {'area': 150201},
                       'conditions_mtask': [175, 3],
                       'conditions_event': [1501009, 1]},
             ('area', 150201))
        self.assertEqual(176, state.main_task)
        play(1502002, {'id': 1502002, 'type': 'talk',
                       'conditions_add': {'npcid': 150201},
                       'conditions_mtask': [176, 4],
                       'conditions_event': [1502001, 1]})
        self.assertEqual(177, state.main_task)
        play(9012001, {'id': 9012001, 'type': 'toarea',
                       'conditions_add': {'area': 901201},
                       'conditions_mtask': [177, 3],
                       'conditions_event': [1502002, 1]},
             ('area', 901201))
        self.assertEqual(178, state.main_task)
        play(1501010, {'id': 1501010, 'type': 'toarea',
                       'conditions_add': {'area': 150102},
                       'conditions_mtask': [178, 3],
                       'conditions_event': [9012001, 1]},
             ('area', 150102))
        self.assertEqual(179, state.main_task)
        play(1501011, {'id': 1501011, 'type': 'toarea',
                       'conditions_add': {'area': 150103},
                       'conditions_mtask': [179, 3],
                       'conditions_event': [1501010, 1]},
             ('area', 150103))
        play(2201001, {'id': 2201001, 'type': 'tomap',
                       'conditions_add': {'map': 1601},
                       'conditions_mtask': [179, 4],
                       'conditions_event': [1501011, 1]},
             ('map', 1601))
        self.assertEqual(180, state.main_task)
        play(9105001, {'id': 9105001, 'type': 'toarea',
                       'conditions_add': {'area': 910501},
                       'conditions_mtask': [180, 3],
                       'conditions_event': [2201001, 1]},
             ('area', 910501))
        play(9107001, {'id': 9107001, 'type': 'tomap',
                       'conditions_add': {'map': 9107},
                       'conditions_mtask': [180, 4],
                       'conditions_event': [9105001, 1]},
             ('map', 9107))
        self.assertEqual(181, state.main_task)
        play(9107006, {'id': 9107006, 'type': 'talk',
                       'conditions_add': {'npcid': 910702},
                       'conditions_mtask': [181, 4],
                       'conditions_event': [9107001, 1]})
        self.assertEqual(182, state.main_task)
        self.assertEqual(3, state.main_state)

    def test_x_ship_launch_reaches_task_136(self):
        """119014 builds the ship and hands task 135 to the license test."""
        from event_runtime import EventRuntime
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 135, 4
        trigger = {'id': 119014, 'type': 'talk',
                   'conditions_add': {'npcid': 590901},
                   'conditions_mtask': [135, 4]}
        runtime = EventRuntime(self.data, state)
        runtime.start('pEvent119014.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume('win' if request.kind == 'fight' else
                           (True if request.kind == 'accepttask' else
                            ([] if request.kind == 'costtaskitem' else None)))
        self.assertEqual(136, state.main_task)
        self.assertEqual(3, state.main_state)
        self.assertEqual(1, state.events.get('119014', 0))

    def test_x_license_fight_reaches_task_137(self):
        """119015's test fight must submit 136 and start the sea voyage."""
        from event_runtime import EventRuntime
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 136, 3
        trigger = {'id': 119015, 'type': 'talk',
                   'conditions_add': {'npcid': 11928},
                   'conditions_mtask': [136, 3, 136, 4]}
        runtime = EventRuntime(self.data, state)
        runtime.start('pEvent119015.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume('win' if request.kind == 'fight' else
                           (True if request.kind == 'accepttask' else
                            ([] if request.kind == 'costtaskitem' else None)))
        self.assertEqual(137, state.main_task)
        self.assertEqual(3, state.main_state)
        self.assertEqual(1, state.events.get('119015', 0))

    def test_x_cloth_errand_starts_task_134(self):
        """203006 takes the cloth blueprint and asks for 500k medals."""
        from event_runtime import EventRuntime
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 133, 4
        state.inventory['270085'] = 1
        trigger = {'id': 203006, 'type': 'talk',
                   'conditions_add': {'npcid': 20315},
                   'conditions_mtask': [133, 4]}
        runtime = EventRuntime(self.data, state)
        runtime.start('pEvent203006.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume(True if request.kind == 'accepttask' else
                           ([] if request.kind == 'costtaskitem' else None))
        self.assertEqual(134, state.main_task)
        self.assertEqual(3, state.main_state)
        self.assertEqual(1, state.events.get('203006', 0))
        self.assertEqual(0, state.inventory.get('270085', 0))

    def test_x_cloth_errand_finishes_with_medals(self):
        """203007 consumes 500000 race medals and hands over 100 cloth."""
        from event_runtime import EventRuntime
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 134, 4
        state.inventory['700008'] = 500000
        trigger = {'id': 203007, 'type': 'talk',
                   'conditions_add': {'npcid': 20315},
                   'conditions_mtask': [134, 3, 134, 4]}
        runtime = EventRuntime(self.data, state)
        runtime.start('pEvent203007.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume(True if request.kind == 'accepttask' else
                           ([] if request.kind == 'costtaskitem' else None))
        self.assertEqual(135, state.main_task)
        self.assertEqual(4, state.main_state)
        self.assertEqual(1, state.events.get('203007', 0))
        self.assertEqual(0, state.inventory.get('700008', 0))
        self.assertEqual(100, state.inventory.get('270088', 0))

    def test_x_metal_collection_finishes_task_132(self):
        """100 type-2 rocks -> 503006 hands over 100 metal and starts 133."""
        from event_runtime import EventRuntime
        from game_state import GameState
        state = GameState(self.data.tables)
        state.initialize(1)
        state.add_preset(next(iter(self.data.tables['InitPet'])))
        state.main_task, state.main_state = 132, 4
        state.task_counts['main:132'] = [100]
        state.events['5301002'] = 1
        trigger = {'id': 503006, 'type': 'tomap',
                   'conditions_add': {'map': 503},
                   'conditions_mtask': [132, 4],
                   'conditions_event': [5301002, 1]}
        runtime = EventRuntime(self.data, state)
        runtime.start('pEvent503006.json', trigger)
        while True:
            request = runtime.next()
            if request is None:
                break
            runtime.resume(True if request.kind == 'accepttask' else
                           ([] if request.kind == 'costtaskitem' else None))
        self.assertEqual(133, state.main_task)
        # 133 is a talk-to-Mary condition; TaskProgress enters 4 immediately.
        self.assertEqual(4, state.main_state)
        self.assertEqual(1, state.events.get('503006', 0))
        self.assertEqual(100, state.inventory.get('270087', 0))

    def test_x_wood_collection_finishes_task_129(self):
        """300 cut trees -> 305006 hands over 300 wood and starts task 130."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 129, 3
                app.state.events['312001'] = 1
                app.state.task_counts['main:129'] = [300]
                app.load_map(305)
                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '305006')
                app.runtime.start('pEvent305006.json', trigger)
                app.drive()
                for _ in range(30000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                    'tapscreen', 'button'):
                        app.interact()
                    elif app.ui_open:
                        app.close_ui('yes')
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.runtime.running:
                        app.drive()
                    else:
                        break
                self.assertFalse(app.runtime.running, app.event_issue)
                self.assertEqual(305, app.map_id)
                self.assertEqual(130, app.state.main_task)
                self.assertEqual(300, app.state.inventory.get('270086'))
                self.assertEqual(1, app.state.events.get('305006', 0))
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

    def test_x_postgame_blueprint_reaches_task_124(self):
        """Postgame 121 -> 122 -> 123 must hand over the boat blueprint."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 121, 3
                app.state.events['7228005'] = 1

                def play():
                    for _ in range(12000):
                        root.update()
                        time.sleep(.001)
                        request = app.display_request
                        if request and request.kind in ('talk', 'aside', 'airtalk',
                                                         'tapscreen', 'button'):
                            app.interact()
                        elif app.pending_wait:
                            app.pending_wait = None
                            app.runtime.resume()
                            app.drive()
                        elif app.battle:
                            app.battle.result = 'win'
                            app.finish_battle()
                        elif app.ui_open:
                            app.close_ui('yes')
                        elif (app.runtime.running and not request and not app.pending_wait
                              and not app.battle):
                            app.drive()
                        elif not app.runtime.running and not request:
                            return

                app.load_map(602)
                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '602012')
                app.runtime.start('pEvent602012.json', trigger)
                app.drive()
                play()
                self.assertEqual(122, app.state.main_task)

                app.load_map(7202)
                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '7202001')
                app.runtime.start('pEvent7202001.json', trigger)
                app.drive()
                play()
                self.assertEqual(123, app.state.main_task)

                app.x, app.y = 800, 288
                app.process_player_areas(force=True)
                play()
                self.assertEqual(4, app.state.main_state)
                self.assertEqual([1], app.state.task_counts['main:123'])

                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '7202003')
                app.runtime.start('pEvent7202003.json', trigger)
                app.drive()
                play()
                self.assertFalse(app.runtime.running)
                self.assertEqual(602, app.map_id)
                self.assertEqual(124, app.state.main_task)
                self.assertEqual(1, app.state.events.get('7202003', 0))
                self.assertEqual(1, app.state.events.get('602013', 0))
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

    def test_x_final_boss_and_ending_reach_task_121(self):
        """5708001 win -> 7228 -> 7228005 ending must submit 120 and reach 602."""
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 120, 3
                app.state.events['5707001'] = 1
                # The room flashback is an earlier visit on the normal route.
                app.state.events['7228001'] = 1
                app.load_map(5708)
                trigger = next(r for r in app.runtime.triggers
                               if str(r['id']) == '5708001')
                app.runtime.start('pEvent5708001.json', trigger)
                app.drive()
                battle = None
                for _ in range(25000):
                    root.update()
                    time.sleep(.001)
                    request = app.display_request
                    if request and request.kind in ('talk', 'aside', 'airtalk',
                                                     'tapscreen', 'button'):
                        app.interact()
                    elif app.pending_wait:
                        app.pending_wait = None
                        app.runtime.resume()
                        app.drive()
                    elif app.battle and battle is None:
                        battle = app.battle
                        battle.result = 'win'
                        app.finish_battle()
                    elif app.ui_open:
                        app.close_ui('yes')
                    elif (app.runtime.running and not request and not app.pending_wait
                          and not app.battle):
                        app.drive()
                    elif not app.runtime.running and not request:
                        break
                self.assertIsNotNone(battle, app.event_issue)
                self.assertFalse(app.runtime.running)
                self.assertEqual(602, app.map_id)
                self.assertEqual(121, app.state.main_task)
                self.assertEqual(1, app.state.events.get('5708001', 0))
                self.assertEqual(1, app.state.events.get('7228005', 0))
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

    def test_x_task119_counts_each_kings_shield(self):
        """Task 119 requires all three authored King's Shield victories."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            from game_state import GameState
            from task_progress import TaskProgress
            state = GameState(self.data.tables)
            state.main_task, state.main_state = 119, 3
            progress = TaskProgress(state)
            for npc in (5705011, 5706011):
                progress.update('fight', 2, 1, npc, -1)
                self.assertEqual(3, state.main_state)
            progress.update('fight', 2, 1, 5704011, -1)
            self.assertEqual(4, state.main_state)
            self.assertEqual([1, 1, 1], state.task_counts['main:119'])

    def test_x_missed_map_arrival_survives_restore(self):
        """The same recovery must run when the stuck save is loaded again."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.load_map(5205)
                app.state.main_task, app.state.main_state = 115, 4
                app.state.task_counts['main:115'] = [1]
                app.state.events['5202001'] = 1
                app.map_id, app.x, app.y = 5205, 960, 1088
                self.assertTrue(app.save())
                restored = NativeGame(root, self.data)
                self.assertTrue(restored.restore())
                self.assertTrue(restored.runtime.running)
                self.assertEqual('pEvent5205001.json', restored.runtime.file)
                self.assertEqual(115, restored.state.main_task)
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

    def test_x_missed_map_arrival_starts_original_plot(self):
        """A task becoming ready inside its map still starts the tomap plot."""
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data)
                if app.runtime.running:
                    app.runtime.finish()
                app.display_request = None
                app.state.main_task, app.state.main_state = 115, 4
                app.state.events['5202001'] = 1
                app.load_map(5205)
                self.assertTrue(app.repair_ready_map_story())
                self.assertTrue(app.runtime.running)
                self.assertEqual('pEvent5205001.json', app.runtime.file)
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

    def test_x_opening_shows_the_original_logo_layers(self):
        """LogoLayer's SP/CP/CR images must precede OpeningUI."""
        import time as clock
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data, show_opening=True)
                self.assertIsNotNone(app.loading)
                loading = app.make_frame()
                self.assertEqual((960, 576), loading.size)
                self.assertGreater(loading.convert('RGB').getextrema()[0][1], 0)
                app.loading = (app.loading[0], 0, app.loading[2])
                app.opening_input()
                self.assertIsNone(app.loading)
                self.assertIsNotNone(app.splash)
                stages = app.splash[0]
                self.assertEqual(
                    ['Logo/splogo.png', 'Logo/logo.png', 'Logo/copyrightLogo.png'],
                    [path for path, _ in stages])
                frame = app.make_frame()
                self.assertEqual((960, 576), frame.size)
                self.assertGreater(frame.getbbox()[2], 0)
                for _ in stages:
                    app.splash = (app.splash[0], app.splash[1],
                                  clock.monotonic()-10)
                    app.opening_input()
                self.assertIsNone(app.splash)
                self.assertIsNotNone(app.opening)
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

    def test_x_opening_respects_saved_audio_switches(self):
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            (Path(save)/'slot1.json').write_text(
                '{"presentation": {"music_enabled": false, "effects_enabled": false}}',
                encoding='utf-8')
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                app = NativeGame(root, self.data, show_opening=True)
                self.assertFalse(app.audio.music_enabled)
                self.assertFalse(app.audio.effects_enabled)
                self.assertIsNotNone(app.opening)
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

    def test_x_screen_type_white_overlay(self):
        import time
        with tempfile.TemporaryDirectory() as save:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = save
            root = tk.Tk()
            root.withdraw()
            try:
                from pc_game import NativeGame
                from event_runtime import Request
                app = NativeGame(root, self.data)
                app.apply_visual(Request('screen', 0, 0, {'parameters': {'type': 1}}))
                self.assertTrue(app.screen_white)
                self.assertFalse(app.screen_black)
                app.screen_fade_until = time.monotonic()+1
                frame = app.make_frame()
                pixel = frame.convert('RGB').getpixel((frame.width//2, frame.height//2))
                self.assertGreater(min(pixel), 220)
                app.apply_visual(Request('screenclose', 0, 0, {'parameters': {}}))
                self.assertFalse(app.screen_white)
                self.assertFalse(app.screen_black)
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

    def test_x_opening_and_battle_timelines(self):
        from csb_render import CocosUI
        ui = CocosUI(self.data)
        for name in ('OpeningUI', 'BattleStartEffectUI'):
            layout = ui.layout(name)
            duration = int(layout['action']['duration'])
            for frame in range(0, duration+1, 20):
                art = ui.render(name, (800, 480), timeline_frame=frame)
                self.assertIsNotNone(art, f'{name} frame {frame}')

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
                self.assertEqual(app.audio.requested, 'BGM_101.mp3')
                frame = app.make_frame()
                self.assertEqual(frame.size, (960, 576))
                app.opening_input(skip=True)
                root.update()
                self.assertIsNone(app.opening)
                self.assertNotEqual(app.audio.requested, 'BGM_101.mp3')
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