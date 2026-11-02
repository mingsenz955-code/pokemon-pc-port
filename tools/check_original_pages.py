"""Original task/guide/pet-selection assets and event behavior, no live windows."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from check_story_motion import DATA
import check_spine_animation as spine_checks
from game_state import GameState
from task_page import TaskPage
from task_guide import TaskGuide
from guide import Guide
from scene_ui import SceneUI
from daily_tasks import DailyTasks
from pc_game import NativeGame


class OriginalPages(unittest.TestCase):
    def make_page(self):
        state = GameState(DATA.tables, 71)
        state.main_task, state.main_state = 129, 3
        state.task_counts['main:129'] = [42]
        app = SimpleNamespace(data=DATA, state=state, closed=[], ui_info=None)
        app.show_reward = lambda title, rewards: None
        app.close_ui = lambda result: app.closed.append(result)
        return TaskPage(app)

    def click(self, page, key):
        page.render()
        rect = page.hits[key]
        x, y = (rect[0]+rect[2])/2, (rect[1]+rect[3])/2
        page.press(x, y)
        page.release(x, y)

    def test_task_page_uses_original_geometry_and_no_main_receive(self):
        page = self.make_page()
        image = page.render()
        self.assertEqual((800, 480), image.size)
        self.assertEqual([88, 98, 374, 417], page.rects['mainItem_ListView'])
        self.assertNotIn('receive_Button', page.hits)
        self.assertEqual(255, image.getpixel((100, 200))[3], 'transparent editor panel erased background')
        self.assertFalse(page.ui.diagnostics)
        self.assertIn('42/300', page.info())

    def test_original_tabs_and_close_work_on_release(self):
        page = self.make_page()
        self.click(page, 'tag_3_Button')
        self.assertEqual('daily', page.page)
        self.assertEqual(8, len(page.rows))
        self.click(page, 'close_Button')
        self.assertEqual(['no'], page.app.closed)

    def test_scroll_reveals_eighth_daily_row_and_drag_does_not_claim(self):
        page = self.make_page()
        page.select_page('daily')
        page.wheel(-10)
        page.render()
        self.assertIn('task_row_7', page.hits)
        self.click(page, 'task_row_7')
        self.assertEqual(7, page.selected)
        page.press(200, 200)
        page.motion(200, 300)
        page.release(200, 300)
        self.assertEqual(7, page.selected)

    def test_daily_receive_gives_actual_reward_only_once(self):
        page = self.make_page()
        page.select_page('daily')
        daily = DailyTasks(page.app.state)
        daily.record('talk', 100)
        page.sync()
        page.selected = next(i for i, r in enumerate(page.rows) if r[2] == 4)
        key, row, status, counts = page.rows[page.selected]
        before = page.app.state.payload()
        page.receive()
        self.assertTrue(daily.claimed(key))
        after = page.app.state.payload()
        page.receive()
        self.assertNotEqual(before['state']['inventory'], after['state']['inventory'])
        self.assertEqual(after, page.app.state.payload())

    def test_native_canvas_routes_scaled_task_pointer_and_escape(self):
        page = self.make_page()
        page.render()
        app = SimpleNamespace(task_page=page, WIDTH=960, HEIGHT=576)
        rect = page.hits['tag_2_Button']
        e = SimpleNamespace(x=(rect[0]+rect[2])*.6, y=(rect[1]+rect[3])*.6)
        NativeGame.task_page_event(app, 'press', e)
        NativeGame.task_page_event(app, 'release', e)
        self.assertEqual('branch', page.page)

    def test_arrow_is_two_tiles_away_with_original_half_second_pulse(self):
        app = SimpleNamespace(x=100, y=100, map=SimpleNamespace(tw=64, th=64),
                              face='standdown', scene_animation_time=0)
        guide = TaskGuide(app)
        guide.point = lambda: (500, 100)
        self.assertEqual((228, 100, 0), guide.pose())
        app.scene_animation_time = .5
        self.assertEqual((245, 100, 0), guide.pose())
        app.scene_animation_time = 1
        self.assertEqual((228, 100, 0), guide.pose())
        guide.point = lambda: (100, 0)
        self.assertEqual((100, -28, 90), guide.pose())

    def test_task_arrow_is_hidden_without_a_navigation_request(self):
        app = SimpleNamespace(guide=SimpleNamespace(active=False, click_mode=False, waypoints=[]))
        self.assertIsNone(TaskGuide(app).point())

    def test_up_menu_uses_current_map_exits_and_bank_type_four(self):
        app = SimpleNamespace(data=DATA, state=GameState(DATA.tables, 1), map=DATA.load_map(101))
        scene = SceneUI(app)
        self.assertEqual((1, 4, 3, 2, 5), scene.SHOP_TYPES)
        self.assertEqual('10107', scene.shop_exits()[4]['name'])
        self.assertEqual(0, scene.groups['up']['target'])

    def test_battle_pet_selection_uses_original_petselect_layout(self):
        ui, battle = spine_checks.SpineChecks().make_ui()
        ui.screen = 'pets'
        frame = ui.render()
        self.assertIn('pet_0', ui.hits)
        self.assertIn('pet_back', ui.hits)
        self.assertEqual((960, 576), frame.size)
        self.assertGreater(ui.hits['pet_0'][0], 200)
        self.assertFalse(ui.app.cocos_ui.diagnostics)

    def test_owned_battle_item_uses_immediately_without_fake_confirmation(self):
        ui, battle = spine_checks.SpineChecks().make_ui()
        item = next(key for key, row in DATA.tables['PetItem'].items()
                    if int(row['type']) == 1 and str(row['parameters']).startswith('1,')
                    and DATA.tables['Item'][key]['useType'] == '1')
        ui.app.state.inventory = {item: 2}
        battle.player_active.hp = 1
        ui.screen, ui.item_filter = 'items', 1
        ui.render()
        ui._action('itemMenu_1_Button')
        self.assertEqual(1, ui.app.state.count(item))
        self.assertEqual('main', ui.screen)
        self.assertEqual(1, battle.round)


if __name__ == '__main__':
    unittest.main(verbosity=2)
