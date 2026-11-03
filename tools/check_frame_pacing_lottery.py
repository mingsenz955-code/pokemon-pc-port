"""Visual preservation, buffer reuse and original lottery sequencing/transactions."""
import copy
import json
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops, ImageTk
import check_single_window_flows as fixtures


class FrameLotteryChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    open = fixtures.SingleWindowChecks.open
    click = fixtures.SingleWindowChecks.click
    save_panel = fixtures.SingleWindowChecks.save_panel

    def reveal(self):
        movie = self.app.lottery_animation
        movie.tick(elapsed=movie.info_at+.01, schedule=False)
        return movie

    def test_reused_canvas_photo_updates_changed_pixels_and_resizes(self):
        a = self.app
        one = Image.new('RGBA', (a.WIDTH, a.HEIGHT), 'red')
        a.viewport.present(one)
        name = str(a.tk_image)
        one.paste('blue', (0, 0, a.WIDTH, a.HEIGHT))
        a.viewport.present(one)
        self.assertEqual(str(a.tk_image), name)
        self.assertEqual(ImageTk.getimage(a.tk_image).getpixel((10, 10)), (0, 0, 255, 255))
        a.viewport.scale = 1.5
        a.viewport.present(one)
        self.assertEqual(a.tk_image.width(), round(a.WIDTH*1.5))
        self.assertEqual(ImageTk.getimage(a.tk_image).getpixel((10, 10)), (0, 0, 255, 255))

    def test_reused_modal_photo_does_not_freeze_or_lose_alpha_composition(self):
        self.open(47)
        a = self.app
        layer = Image.new('RGBA', (800, 480), (255, 0, 0, 100))
        a.ui_art_label.set_layer(layer)
        name = str(a.ui_art_label.composited_image)
        layer.paste((0, 255, 0, 120), (0, 0, 800, 480))
        a.ui_art_label.set_layer(layer)
        self.assertEqual(name, str(a.ui_art_label.composited_image))
        expected = a.ui_art_label.backdrop.copy()
        expected.alpha_composite(layer)
        actual = ImageTk.getimage(a.ui_art_label.composited_image)
        self.assertIsNone(ImageChops.difference(actual.convert('RGB'), expected.convert('RGB')).getbbox())

    def test_cached_pet_poses_match_original_full_layer_clipping(self):
        self.open(47)
        a, page = self.app, self.app.original_page
        for age in (.0, .17, .42, 1.02, .17):
            reference = page.layer.copy()
            for species, point, area, limit in page.animated_pets:
                duration = a.data.pet_clip_duration(species, 'stand')
                index = int((age % duration if duration else age)*30)
                art = a.data.pet_frame(species, 'stand', index, True, fps=30, limit=max(220, limit))
                setup = a.data.pet_image(species)
                ratio = min(limit/setup.width, limit/setup.height)*setup.info.get('pixels_per_unit', 1)/art.info.get('pixels_per_unit', 1)
                origin = art.info.get('origin', (art.width/2, art.height))
                art = art.resize((max(1, round(art.width*ratio)), max(1, round(art.height*ratio))), Image.Resampling.LANCZOS)
                layer = Image.new('RGBA', reference.size)
                layer.alpha_composite(art, (round(point[0]-origin[0]*ratio), round(point[1]-origin[1]*ratio)))
                x, y, right, bottom = map(round, area)
                reference.alpha_composite(layer.crop((x, y, right, bottom)), (x, y))
            actual = page.pet_frame(page.layer.copy(), age)
            self.assertIsNone(ImageChops.difference(reference, actual).getbbox())
        self.assertLessEqual(len(page._pet_pose_cache), 96)

    def test_lossless_baked_frames_match_live_original_renderer(self):
        data = self.app.data
        for name, clip, frame in [('niudanji', 'Animation1', 30), ('niudanji', 'Animation2', 50),
                                 ('niudanji', 'Animation3_3', 60), ('niudanji', 'Animation4_2', 87),
                                 ('ndchongwubeijingguang', 'Animation1', 20)]:
            cached = data.armature(name, clip, frame, viewport=(800, 480))
            self.assertIsNotNone(data._lottery_cache_manifest)
            live = data._render_armature(name, clip, frame)
            if name == 'niudanji':
                rendered = []
                for art in (cached, live):
                    canvas = Image.new('RGBA', (800, 480), '#475b6f')
                    ox, oy = art.info['origin']
                    canvas.alpha_composite(art, (-ox, 480-oy))
                    rendered.append(canvas)
                self.assertEqual(rendered[0].tobytes(), rendered[1].tobytes())
            else:
                self.assertEqual(cached.info['origin'], live.info['origin'])
                self.assertEqual(cached.tobytes(), live.tobytes())

    def test_all_three_draws_use_native_phases_and_opaque_result_background(self):
        a = self.app
        a.state.functions['8'] = 1
        for kind, key in [(1, 'draw_1_Button'), (2, 'draw_2_Button'), (3, 'draw_3_1_Button')]:
            with self.subTest(kind=kind):
                self.open(68)
                before = len(a.state.pets+a.state.bank)
                self.click(key)
                movie = a.lottery_animation
                self.assertEqual(movie.clips, ['Animation1', 'Animation2', f'Animation3_{kind}',
                                                'Animation4_1' if kind == 1 else 'Animation4_2'])
                self.assertEqual(a.original_page.specs[0][0], 'LuckyDrawEffectUI')
                self.assertFalse(any(k.endswith('/confirm_Button') for k in a.ui_hits))
                snapshot = copy.deepcopy(a.state.payload())
                movie.tick(elapsed=.7, schedule=False)
                self.assertEqual(a.ui_base_layer.getchannel('A').getextrema(), (255, 255))
                self.save_panel('lottery-native-machine')
                count = 3 if kind == 3 else 1
                for index in range(count):
                    self.reveal()
                    self.assertEqual(a.original_page.specs[0][0], 'LuckyDrawPetInfoUI')
                    self.assertEqual(a.ui_base_layer.getchannel('A').getextrema(), (255, 255))
                    self.assertEqual(a.state.payload(), snapshot)
                    self.save_panel('lottery-native-result')
                    self.click('confirm_Button')
                    if index+1 < count:
                        self.assertEqual(movie.clips, ['Animation4_2'])
                self.assertEqual(len(a.state.pets+a.state.bank), before+count)
                self.assertEqual(a.original_page.specs[0][0], 'LuckyDrawUI')
                self.assertIsNone(a.lottery_animation)

    def test_sound_events_pause_resume_and_early_confirm_are_not_repeated(self):
        a = self.app
        a.state.functions['8'] = 1
        self.open(68)
        with patch.object(a.audio, 'pause_music') as pause, patch.object(a.audio, 'resume_music') as resume, patch.object(a.audio, 'effect') as sound:
            self.click('draw_2_Button')
            movie = a.lottery_animation
            movie.confirm()
            self.assertEqual(movie.index, 0)
            for _ in range(3):
                movie.tick(elapsed=movie.reveal_at+.1, schedule=False)
            self.assertEqual([call.args[0] for call in sound.call_args_list], ['SE_UI_32.mp3', 'SE_UI_33.mp3'])
            self.assertEqual(pause.call_count, 1)
            self.reveal()
            self.click('confirm_Button')
            self.assertEqual(resume.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
