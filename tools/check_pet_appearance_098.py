"""Original name quality colors and shiny tints remain independent and persistent."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageChops, ImageDraw
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
from check_restoration_097 import DATA, host
from original_pages import Page
from pet_appearance import QUALITY_COLORS, FLASH_TARGETS, quality_color, flash_color, pet_flash
from csb_render import CocosUI

OUT = ROOT/'outputs/verification/0.2.98'
OUT.mkdir(parents=True, exist_ok=True)
BASE, FLASH = next((k, r['flashPetId']) for k, r in DATA.tables['Pet'].items()
                   if r.get('flashPetId') in DATA.tables['Pet']
                   and r['filePath'] == DATA.tables['Pet'][r['flashPetId']]['filePath'])


class Appearance(unittest.TestCase):
    def test_quality_palette_matches_native_initializer(self):
        expected = [(255,255,255), (1,127,13), (0,123,180), (146,0,177), (255,229,8)]
        for quality, rgb in enumerate(expected, 1):
            self.assertEqual(rgb, quality_color(SimpleNamespace(quality=quality)))

    def test_every_flash_record_is_separate_from_quality(self):
        self.assertEqual(149, sum(r['flash'] == '1' for r in DATA.tables['Pet'].values()))
        self.assertEqual('0', DATA.tables['Pet'][BASE]['flash'])
        self.assertEqual('1', DATA.tables['Pet'][FLASH]['flash'])
        image = Image.new('RGBA', (4,4), (200, 150, 100, 128))
        for quality in range(1,6):
            ordinary = pet_flash(DATA, BASE, image, .4)
            shiny = pet_flash(DATA, FLASH, image, .4)
            self.assertIs(ordinary, image)
            self.assertNotEqual(image.getpixel((0,0)), shiny.getpixel((0,0)))
            self.assertEqual(128, shiny.getpixel((0,0))[3])

    def test_flash_uses_all_fifteen_native_tint_stages(self):
        self.assertEqual((255,255,255), flash_color(0))
        for i, rgb in enumerate(FLASH_TARGETS):
            self.assertEqual(rgb, flash_color((i+1)*.4), i)
        self.assertEqual((60,176,73), flash_color(6))
        self.assertEqual(FLASH_TARGETS[0], flash_color(6.4))

    def test_tint_does_not_mutate_pose_or_alpha_or_origin(self):
        image = DATA.pet_image(FLASH)
        before = image.tobytes()
        result = pet_flash(DATA, FLASH, image, .4)
        self.assertEqual(before, image.tobytes())
        self.assertEqual(image.info['origin'], result.info['origin'])
        self.assertEqual(image.getchannel('A').tobytes(), result.getchannel('A').tobytes())
        self.assertIsNotNone(ImageChops.difference(image.convert('RGB'), result.convert('RGB')).getbbox())

    def test_original_text_nodes_render_actual_quality_colors(self):
        ui = CocosUI(DATA)
        for rgb in list(QUALITY_COLORS.values())[:5]:
            frame = ui.render('PetListItemUI', (320,110), visible={'add_Panel':False}, colors={'name_Text': rgb}, text={'name_Text':'测试品质'})
            colors = frame.convert('RGB').getcolors(frame.width*frame.height)
            self.assertGreater(sum(count for count, pixel in colors if max(abs(a-b) for a,b in zip(pixel,rgb)) <= 6), 5, rgb)

    def test_party_page_shiny_animation_continues_over_pose_loops(self):
        app = SimpleNamespace(data=DATA, cocos_ui=CocosUI(DATA))
        page = Page(app, 'PetListUI')
        page.animated_pets.append((FLASH, (400,300), (200,50,600,400), 160))
        original = DATA.pet_clip_duration(FLASH, 'stand')
        frames = [page.pet_frame(Image.new('RGBA',(800,480)), elapsed)
                  for elapsed in (.4, original+.4, original*2+.4)]
        self.assertTrue(all(frame.getbbox() for frame in frames))
        self.assertTrue(any(ImageChops.difference(frames[0].convert('RGB'), frame.convert('RGB')).getbbox()
                            for frame in frames[1:]))

    def test_battle_pose_cache_preserves_shiny_animation(self):
        ui = host()
        unit = ui.battle.player_active
        unit.pet.species = FLASH
        layers = []
        for age in (.4,.8):
            ui.anim_idle = age*25
            layer = Image.new('RGBA',(960,576))
            ui._draw_pet(layer, unit, (300,400), 250)
            layers.append(layer)
        self.assertIsNotNone(ImageChops.difference(layers[0].convert('RGB'), layers[1].convert('RGB')).getbbox())
        unit.pet.quality = 2
        ui._hud_layer(False)
        before = len(ui._hud_cache)
        unit.pet.quality = 4
        ui._hud_layer(False)
        self.assertEqual(before+1, len(ui._hud_cache))


def visuals():
    sheet = Image.new('RGB',(1200,650),(32,42,53))
    draw = ImageDraw.Draw(sheet)
    ui = CocosUI(DATA)
    for i, rgb in enumerate(list(QUALITY_COLORS.values())[:5]):
        card = ui.render('PetListItemUI', (320,110), visible={'add_Panel':False}, colors={'name_Text':rgb}, text={'name_Text':'品质 '+str(i+1)})
        card.thumbnail((235,110))
        sheet.paste(card,(i*240,5),card)
    setup = DATA.pet_image(FLASH)
    for i, age in enumerate((0,.4,1.2,2,2.8,3.6,4.4,5.2)):
        art = pet_flash(DATA, FLASH, setup, age).copy()
        art.thumbnail((230,220))
        x,y=(i%4)*300+150-art.width//2,(i//4)*255+150
        sheet.paste(art,(x,y),art)
        draw.text(((i%4)*300+18,y+220),f'flash t={age:.1f}s',fill='white')
    sheet.save(OUT/'pet-colors-and-flash.jpg',quality=92)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Appearance))
    if result.wasSuccessful(): visuals()
    (OUT/'pet-appearance-checks.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}),encoding='utf-8')
    sys.exit(not result.wasSuccessful())
