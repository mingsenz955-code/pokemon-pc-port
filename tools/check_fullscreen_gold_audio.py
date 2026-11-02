"""Isolated real Tk input, offline purchases and original audio verification."""
import json
import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import ImageTk
import check_single_window_flows as fixtures
from game_audio import GameAudio
from game_state import GameState
from daily_tasks import DailyTasks
from PIL import ImageChops


class EditionChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    open = fixtures.SingleWindowChecks.open
    click = fixtures.SingleWindowChecks.click
    save_panel = fixtures.SingleWindowChecks.save_panel

    def test_all_original_cash_prices_are_fen_converted_to_gold(self):
        a = self.app
        original = json.loads((a.data.root/'tables.json').read_text(encoding='utf-8'))
        for key, raw in original['Store'].items():
            actual = a.data.tables['Store'][key]
            if raw['costMoneyType'] == '700003':
                self.assertEqual(actual['costMoneyType'], '700001')
                self.assertEqual(int(actual['costCount']), int(raw['costCount'])*100)
                self.assertNotIn('元', actual['des2'])
            else:
                self.assertEqual(actual['costCount'], raw['costCount'])
                self.assertEqual(actual['costMoneyType'], raw['costMoneyType'])

    def test_alias_costs_aggregate_without_partial_debit_and_save_migration(self):
        state = self.app.state
        state.inventory['700001'] = 249
        with self.assertRaises(ValueError):
            state.consume(['700001', '700003'], [50, 2])
        self.assertEqual(state.count('700001'), 249)
        state.inventory['700001'] = 250
        state.consume(['700001', '700003'], [50, 2])
        self.assertEqual(state.count('700001'), 0)
        state.inventory['700003'] = 600
        state.save(self.app.save_path)
        loaded = GameState.load(state.tables, self.app.save_path)
        self.assertEqual(loaded.count('700001'), 60000)
        self.assertNotIn('700003', loaded.inventory)
        loaded.save(self.app.save_path)
        self.assertEqual(GameState.load(state.tables, self.app.save_path).count('700001'), 60000)

    def test_gold_bundle_confirmation_rewards_limit_and_failure(self):
        a = self.app
        a.state.inventory['700001'] = 1000000
        self.open(63)
        self.assertEqual(a.original_page.specs[0][0], 'ShopUI')
        # First card is original Store 101: 10 yuan -> 100000 gold.
        before = a.state.count('230011')
        self.click('gold_store_0/Layer/root_Panel/buy_Button')
        self.assertEqual(a.original_page.specs[0][0], 'SecondConfirmUI')
        self.click('confirm_Button')
        self.assertEqual(a.state.count('700001'), 900000)
        self.assertEqual(a.state.count('230011'), before+5)
        self.assertEqual(a.original_page.specs[0][0], 'GetItemUI')
        a.state.buy_store('201')
        snapshot = a.state.payload()
        with self.assertRaises(ValueError):
            a.state.buy_store('201')
        self.assertEqual(a.state.payload(), snapshot)
        a.state.inventory['700001'] = 0
        snapshot = a.state.payload()
        with self.assertRaises(ValueError):
            a.state.buy_store('101')
        self.assertEqual(a.state.payload(), snapshot)
        self.save_panel('edition-gold-reward')

    def test_trial_can_be_purchased_permanently_for_gold(self):
        a = self.app
        key = '600001'
        row = a.data.tables['TrialPet'][key]
        price = int(a.data.tables['Store'][row['storeId']]['costCount'])
        trial = a.state.receive_trial_pet(key)
        a.state.inventory['700001'] = price
        self.open(13, par1=key)
        self.click('buy_Button')
        self.click('confirm_Button')
        self.assertEqual(a.state.count('700001'), 0)
        self.assertEqual(trial.trial_id, '')
        self.assertEqual(trial.trial_remaining, -1)
        self.assertIn(trial.species, a.state.encyclopedia)
        self.assertEqual(sum(p.uid == trial.uid for p in a.state.pets), 1)

    def test_gold_evolution_does_not_skip_level_or_consume_materials(self):
        a = self.app
        pet = a.state.pets[0]
        row = a.data.tables['Evolution'][pet.species]
        pet.level = int(row['level'])-1
        a.state.inventory['700001'] = 50000
        with self.assertRaises(ValueError):
            a.state.evolve(pet.uid, use_gold=True)
        self.assertEqual(a.state.count('700001'), 50000)
        pet.level += 1
        a.state.evolve(pet.uid, use_gold=True)
        self.assertEqual(pet.species, row['petId'])
        self.assertEqual(a.state.count('700001'), 0)

    def test_fullscreen_real_canvas_and_modal_scaled_clicks(self):
        a = self.app
        self.root.attributes('-alpha', 0)
        self.root.deiconify()
        self.root.update()
        a.viewport.toggle()
        self.root.update()
        self.assertTrue(self.root.attributes('-fullscreen'))
        from check_inventory_interactions import OUT
        ImageTk.getimage(a.tk_image).save(OUT/'edition-fullscreen-map.png')
        s, (ox, oy) = a.viewport.scale, a.viewport.offset
        self.assertGreater(s, 1)
        with patch.object(a, 'click_walk') as walk:
            a.canvas.event_generate('<Button-1>', x=round(ox+400*s), y=round(oy+240*s))
            self.root.update()
            self.assertAlmostEqual(walk.call_args[0][0], 400, delta=1)
            self.assertAlmostEqual(walk.call_args[0][1], 240, delta=1)
        self.open(46)
        a.ui_window.deiconify()
        self.root.update()
        self.assertAlmostEqual(a.ui_window.winfo_width(), 800*s, delta=1)
        rect = next(r for k, r in a.ui_hits.items() if k.endswith('/close_Button'))
        x, y = round((rect[0]+rect[2])/2*s), round((rect[1]+rect[3])/2*s)
        a.ui_art_label.event_generate('<ButtonPress-1>', x=x, y=y)
        a.ui_art_label.event_generate('<ButtonRelease-1>', x=x, y=y)
        self.root.update()
        self.assertFalse(a.ui_open)
        a.viewport.escape(SimpleNamespace(keysym='Escape'))
        self.root.update()
        self.assertFalse(self.root.attributes('-fullscreen'))

    def test_all_sound_ids_and_all_bgm_native_mp3_decoders(self):
        audio = self.app.audio
        rows = self.app.data.tables['Sound']
        missing = {key for key in rows if audio.resolve(key) is None}
        self.assertEqual(missing, {'4094', '1154', '1155'})  # Absent original effects, not BGM.
        bgm = [r for r in rows.values() if r['name'].startswith('BGM_')]
        self.assertEqual(len(bgm), 34)
        paths = {audio.resolve(r) for r in bgm}
        self.assertEqual(len(paths), 10)
        send = ctypes.windll.winmm.mciSendStringW
        for path in paths:
            alias = 'pocket_verify'
            self.assertEqual(send(f'open "{path}" type mpegvideo alias {alias}', None, 0, None), 0)
            buf = ctypes.create_unicode_buffer(100)
            try:
                self.assertEqual(send(f'status {alias} length', buf, 100, None), 0)
                self.assertGreater(int(buf.value), 0)
            finally:
                send('close '+alias, None, 0, None)

    def test_audio_no_frame_restarts_and_switches_can_mute(self):
        commands = []
        audio = GameAudio(self.app.data, send=lambda command, *_: commands.append(command) or 0)
        audio.music('201')
        audio.music('202')  # Both authored aliases resolve to 213.
        audio.queue.join()
        self.assertEqual(sum(c.startswith('open ') for c in commands), 1)
        audio.music('401', loop=False)
        audio.queue.join()
        self.assertEqual(commands[-1], 'play pocket_bgm from 0')
        audio.set_enabled('music', False)
        audio.queue.join()
        self.assertEqual(commands[-1], 'close pocket_bgm')
        audio.set_enabled('effect', False)
        audio.queue.join()
        n = len(commands)
        audio.effect('5003')
        audio.queue.join()
        self.assertEqual(len(commands), n)
        audio.set_enabled('music', True)
        audio.queue.join()
        self.assertTrue(commands[-1].startswith('play pocket_bgm'))
        audio.close()
        audio.queue.join()

    def test_settings_saved_switches_and_no_music_store(self):
        a = self.app
        self.open(65)
        self.click('music_open_Button')
        self.assertFalse(a.audio.music_enabled)
        self.assertFalse(a.state.presentation['music_enabled'])
        self.click('music_close_Button')
        self.assertTrue(a.audio.music_enabled)
        self.assertFalse(any(k.endswith('/moreGame_Button') for k in a.ui_hits))
        self.open(63)
        for spec in a.original_page.specs:
            if spec[0] == 'ShopGoodsUI':
                self.assertNotIn(spec[2]['text']['name_Text'], ('金币4万', '金币9万', '金币15万'))
        snapshot = a.state.payload()
        with self.assertRaises(ValueError):
            a.state.buy_store('102')
        self.assertEqual(a.state.payload(), snapshot)
        self.save_panel('edition-gold-shop')

    def test_daily_claim_cleans_entire_task_border_and_returns_to_daily(self):
        a = self.app
        daily = DailyTasks(a.state)
        daily.record('fight', daily.required('2'))
        self.open(44, page='daily')
        page = a.task_page
        page.selected = next(i for i, row in enumerate(page.rows) if row[0] == '2')
        a.task_page = None
        clean = a.make_frame()
        a.task_page = page
        # Publish the full task frame, as the real game does before claiming.
        a.viewport.present(a.make_frame())
        page.receive()
        self.assertIsNone(a.task_page)
        canvas = ImageTk.getimage(a.tk_image)
        self.assertIsNone(ImageChops.difference(canvas.convert('RGB'), clean.convert('RGB')).getbbox())
        self.assertEqual(a.original_page.layer.getpixel((60, 40))[3], 0)
        self.assertEqual(a.original_page.specs[0][0], 'GetItemUI')
        self.save_panel('edition-daily-reward')
        snapshot = a.state.payload()
        self.click('confirm_Button')
        self.assertEqual(a.task_page.page, 'daily')
        self.assertTrue(DailyTasks(a.state).claimed('2'))
        a.task_page.selected = next(i for i, row in enumerate(a.task_page.rows) if row[0] == '2')
        a.task_page.receive()
        self.assertEqual(a.state.payload(), snapshot)


if __name__ == '__main__':
    unittest.main(verbosity=2)
