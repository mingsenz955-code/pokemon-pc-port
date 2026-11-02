"""Original scenery masks, real draw ordering and continuous task guidance."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from check_story_motion import DATA, host, move
from game_state import GameState
from guide import Guide, GuideTarget
from mounts import Mounts
from pc_preview import Preview


class TraversalChecks(unittest.TestCase):
    def test_original_tower_four_collision_cells_and_flying_exception(self):
        world = DATA.load_map(101)
        self.assertEqual(348, len(DATA.sprite_tiles()))
        tower = next(o for o in world.objects if o.get('gid') and
                     world.tile_properties(int(o['gid'])).get('spriteId') == '50168')
        tx, ty = int(float(tower['x'])//64), int(float(tower['y'])//64)
        state = GameState(DATA.tables)
        state.rides, state.ride = [500002, 500003, 500005], 0
        mounts = Mounts(state)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x, y = (tx+dx+.5)*64, (ty-dy+.5)*64
            for ride in (0, 500002, 500005):
                state.ride = ride
                self.assertTrue(world.sprite_blocked(x, y, mounts))
                self.assertTrue(world.blocked(x, y, mounts))
            state.ride = 500003
            self.assertFalse(world.sprite_blocked(x, y, mounts))

    def test_shop_door_is_not_replaced_with_image_rectangle(self):
        world = DATA.load_map(101)
        shop = next(o for o in world.objects if o.get('gid') and
                    world.tile_properties(int(o['gid'])).get('spriteId') == '50166')
        tx, ty = int(float(shop['x'])//64), int(float(shop['y'])//64)
        self.assertNotIn((tx, ty), world.sprite_collision)
        self.assertIn((tx-1, ty), world.sprite_collision)
        self.assertIn((tx+1, ty), world.sprite_collision)

    def test_actual_scene_renderer_draws_building_in_front_of_actor_behind_it(self):
        app = SimpleNamespace(WIDTH=200, HEIGHT=200, SCALE=1, DYNAMIC_SCENERY=True,
            x=256, y=200, camera_focus=(256, 200), player_visible=True, face='standdown',
            show_map_label=False, dialogue=None, background=Image.new('RGBA', (500, 500), 'white'))
        building = Image.new('RGBA', (100, 200), 'red')
        building.info['origin'] = (50, 200)
        app.map = SimpleNamespace(scenery=lambda: [(256, 256, building)])
        app.actors = lambda: []
        app.actor_animation = lambda *args: 'standdown'
        app.player_image = lambda face: Image.new('RGBA', (10, 10), 'blue')
        app.camera_origin = lambda: (156, 100)
        frame = Preview.make_frame(app)
        self.assertEqual((255, 0, 0), frame.getpixel((100, 95))[:3])

    def test_guide_uses_elapsed_time_and_reaches_adjacent_tile_center(self):
        app = host(move())
        app.data, app.noclip = DATA, False
        app.map.width = 20
        app.runtime.file, app.runtime.sequence, app.runtime.pending = '', [], None
        app.actors = lambda: [('10109', '20005', 608, 96)]
        app.guide = Guide(app)
        app.guide.start(GuideTarget('npc', 'next quest NPC', 101, 608, 96, npc_id='10109'))
        for _ in range(25):
            app.guide.step(.04)
        self.assertAlmostEqual(416, app.x)
        self.assertTrue(app.guide.active)
        for _ in range(5):
            app.guide.step(.04)
        self.assertTrue(app.guide.active, 'guide stopped two tiles away')
        for _ in range(10):
            app.guide.step(.04)
        self.assertFalse(app.guide.active)
        self.assertAlmostEqual(544, app.x)
        self.assertEqual('standright', app.face)


if __name__ == '__main__':
    unittest.main(verbosity=2)
