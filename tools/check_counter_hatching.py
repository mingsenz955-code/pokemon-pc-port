"""Real original maps/counter regions and native hatch page interactions."""
import copy
import unittest
from types import SimpleNamespace
from PIL import ImageChops
import check_single_window_flows as fixtures
from activities import Activities
from event_runtime import Request
from game_state import GameState, numbers
from battle import make_wild_battle
from game_formulas import hatch_exp


class CounterHatchChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    open = fixtures.SingleWindowChecks.open
    click = fixtures.SingleWindowChecks.click
    save_panel = fixtures.SingleWindowChecks.save_panel

    def reset_script(self):
        a = self.app
        if a.ui_window and a.ui_window.winfo_exists():
            a.ui_window.destroy()
        a.ui_window, a.ui_open = None, False
        a.display_request, a.dialogue, a.pending_wait = None, None, None
        a.runtime.file, a.runtime.sequence, a.runtime.pending = '', [], None
        a.runtime.active_trigger = None
        a.runtime.queue = []
        a.runtime_error = ''
        a.state.main_task, a.state.main_state = 155, 5
        a.state.events['5905001'] = 1

    def test_real_counter_sprite_click_walks_to_original_region_then_opens_correct_page(self):
        a = self.app
        services = [(5802, '580201', 1), (5803, '580302', 3), (5803, '580301', 6),
                    (5804, '580401', 2), (5805, '580501', 5), (5805, '580502', 4)]
        for mid, oid, uiid in services:
            with self.subTest(npc=oid):
                self.reset_script()
                a.load_map(mid, 544, 640 if oid == '580501' else 1120)
                actor = next(t for t in a.actors() if t[0] == oid and 20000 <= int(t[1]) < 30000)
                sprite = a.scene_sprite(actor[1], a.actor_animation(*actor[:2]))
                bx, by, right, bottom = sprite.getbbox()
                candidates = [(x, y) for y in range(by, bottom) for x in range(bx, right) if sprite.getpixel((x, y))[3] > 100]
                px, py = min(candidates, key=lambda p: (p[0]-(bx+right)/2)**2+(p[1]-(by+bottom)/2)**2)
                origin = sprite.info.get('origin', (sprite.width/2, sprite.height))
                cx, cy = a.camera_origin()
                sx = (actor[2]-origin[0]+px)*a.SCALE-cx
                sy = (actor[3]-origin[1]+py)*a.SCALE-cy
                self.assertTrue(0 <= sx < a.WIDTH and 0 <= sy < a.HEIGHT)
                a.on_click(SimpleNamespace(x=sx, y=sy))
                self.assertEqual(a.guide.target.npc_id, oid)
                for _ in range(800):
                    if not a.guide.active:
                        break
                    a.guide.step(.04)
                self.assertFalse(a.guide.active)
                self.assertEqual(a.runtime.file, f'pEventTalk{oid}.json')
                self.assertEqual(a.display_request.kind, 'talk')
                a.interact()  # Advance the actual greeting to its original openui.
                self.assertEqual(int(a.ui_parameters['uiid']), uiid)
                self.assertFalse(a.runtime_error)
                a.close_ui()
                self.assertTrue(a.dialogue)

    def test_entering_counter_region_triggers_greeting_without_remote_talk_or_unlock_bypass(self):
        a = self.app
        self.reset_script()
        a.state.events['5905001'] = 0
        a.load_map(5805, 320, 480)
        a.process_player_areas(force=True)
        self.assertIn('筹备中', a.dialogue)
        a.interact()
        self.assertFalse(a.ui_open)
        self.reset_script()
        a.load_map(5805, 544, 1120)
        a.interact('580501')
        self.assertFalse(a.runtime.running)
        a.x, a.y = 864, 864
        a.process_player_areas(force=True)
        self.assertEqual(a.runtime.file, 'pEventTalk580502.json')
        self.assertIn('银行职员', a.dialogue)

    def put_via_ui(self, key='250006'):
        a = self.app
        for item in a.data.tables['HatchItem']:
            a.state.inventory.pop(item, None)
        a.state.grant(key, 1)
        self.open(5)
        self.click('hatch_0/Layer/root_Panel/putIn_Button')
        self.click('use_Button')
        self.assertEqual(a.state.count(key), 0)
        self.assertEqual(a.original_page.specs[0][0], 'HatchRoomUI')

    def finish_effect(self):
        page = self.app.original_page
        self.assertEqual(page.specs[0][0], 'PetHatchEffectUI')
        self.click('confirm_Button')
        self.assertIs(self.app.original_page, page)  # Invisible early confirm cannot skip.
        early = page.pet_frame(page.frame_at(0), 0)
        late = page.pet_frame(page.frame_at(4), 4)
        self.assertIsNotNone(ImageChops.difference(early.convert('RGB'), late.convert('RGB')).getbbox())
        page.effect_start -= 4
        page.animate()
        self.save_panel('hatch-effect-final')
        self.click('confirm_Button')

    def test_money_hatch_real_bag_choice_native_cards_effect_and_claim(self):
        a = self.app
        self.put_via_ui()
        self.save_panel('hatch-egg')
        self.click('hatch_0/Layer/root_Panel/check_Button')
        self.assertFalse(any(c.winfo_class() == 'Listbox' for c in a.ui_window.winfo_children()))
        self.save_panel('hatch-check')
        before = a.state.count('700001')
        self.click('moneyHatch_Button')
        self.assertEqual(a.state.count('700001'), before-500)
        self.assertEqual(a.state.activities['eggs']['0']['pet']['species'], '100007')
        self.finish_effect()
        self.save_panel('hatch-ready')
        self.click('hatch_0/Layer/root_Panel/takeBack_Button')
        self.assertEqual(a.state.pets[-1].species, '100007')
        self.assertNotIn('0', a.state.activities['eggs'])
        self.click('confirm_Button')
        self.assertEqual(a.original_page.specs[0][0], 'HatchRoomUI')

    def test_material_conditions_errors_and_take_back_preserve_items(self):
        a = self.app
        self.put_via_ui()
        row = a.data.tables['HatchItem']['250006']
        activity = Activities(a.state)
        a.state.inventory['700001'] = 0
        snapshot = a.state.payload()
        with self.assertRaises(ValueError):
            activity.hatch(0, use_money=True)
        self.assertEqual(snapshot, a.state.payload())
        activity.add_hatch_exp(10000)
        self.assertEqual(a.state.activities['eggs']['0']['exp'], int(row['exp']))
        a.state.inventory['240002'] = 0
        snapshot = a.state.payload()
        with self.assertRaises(ValueError):
            activity.hatch(0)
        self.assertEqual(snapshot, a.state.payload())
        a.state.grant('240002', 1)
        a._hatch_room_page(a.ui_info)
        self.click('hatch_0/Layer/root_Panel/hatch_Button')
        self.assertEqual(a.state.count('240002'), 0)
        self.finish_effect()

    def test_take_back_egg_confirm_and_no_script_advance_when_check_closes(self):
        a = self.app
        self.put_via_ui()
        self.click('hatch_0/Layer/root_Panel/check_Button')
        self.click('takeBackEgg_Button')
        self.click('cancel_Button')
        self.assertIn('0', a.state.activities['eggs'])
        self.click('takeBackEgg_Button')
        self.click('confirm_Button')
        self.assertNotIn('0', a.state.activities['eggs'])
        self.assertEqual(a.state.count('250006'), 1)
        self.assertEqual(a.original_page.specs[0][0], 'HatchRoomUI')

    def test_all_ten_egg_rows_slots_scrolling_save_and_full_claim_rollback(self):
        a = self.app
        activity = Activities(a.state)
        for index, key in enumerate(sorted(a.data.tables['HatchItem'])):
            a.state.grant(key, 1)
            activity.put_egg(index, key)
            activity.hatch(index, use_money=True)
        a.state.save(a.save_path)
        loaded = GameState.load(a.data.tables, a.save_path)
        self.assertEqual(loaded.activities['eggs'], a.state.activities['eggs'])
        a.state = loaded
        self.open(5)
        for _ in range(10):
            a.page_wheel(SimpleNamespace(delta=-120))
        self.assertTrue(any(k.startswith('hatch_9/') for k in a.ui_hits))
        a.state.inventory['700004'] = len(a.state.pets)
        a.state.inventory['700005'] = 0
        snapshot = a.state.payload()
        with self.assertRaises(ValueError):
            Activities(a.state).take_egg(9)
        self.assertEqual(snapshot, a.state.payload())

    def test_nested_hatch_check_returns_without_advancing_original_npc_script(self):
        a = self.app
        self.reset_script()
        a.state.grant('250006', 1)
        Activities(a.state).put_egg(0, '250006')
        a.load_map(5805, 320, 480)
        a.process_player_areas(force=True)
        a.interact()
        pending, index = a.runtime.pending, a.runtime.index
        self.assertEqual(pending.kind, 'openui')
        self.click('hatch_0/Layer/root_Panel/check_Button')
        self.click('close_Button')
        self.assertIs(a.runtime.pending, pending)
        self.assertEqual(a.runtime.index, index)
        self.assertEqual(a.original_page.specs[0][0], 'HatchRoomUI')
        a.close_ui()
        self.assertIn('欢迎下次光临', a.dialogue)

    def test_real_battle_rewards_add_hatching_experience_once(self):
        a = self.app
        a.state.grant('250006', 1)
        Activities(a.state).put_egg(0, '250006')
        battle = make_wild_battle(a.data.tables, a.state.pets, 607001, a.state.rng)
        battle.choose_item('220006')
        self.assertEqual(battle.result, 'caught')
        self.assertTrue(battle.apply_rewards(a.state))
        expected = hatch_exp(sum(row[1] for row in battle.exp_gained))
        self.assertEqual(a.state.activities['eggs']['0']['exp'], expected)
        self.assertFalse(battle.apply_rewards(a.state))
        self.assertEqual(a.state.activities['eggs']['0']['exp'], expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
