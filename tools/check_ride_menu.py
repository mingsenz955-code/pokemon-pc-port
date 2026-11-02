"""Original riding HUD regressions. Uses recovered CSB/tables, no live saves or windows."""
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from PIL import Image, ImageChops
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from csb_render import CocosUI
from game_state import GameState
from scene_ui import SceneUI
from pc_game import NativeGame
from mounts import Mounts
DATA = OriginalData(ROOT/'original-1.20.4')

class RideMenuChecks(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.app=SimpleNamespace(WIDTH=960, HEIGHT=576, cocos_ui=CocosUI(DATA), data=DATA,
            state=GameState(DATA.tables, seed=42), map=DATA.load_map(101), x=0, y=0)
        self.app.state.rides=[]
        self.app.state.ride=0
        for name in ('save_ui','tasks_ui','guide_toggle','lottery_ui','store_ui','recharge_ui',
                     'bag_ui','pets_ui','illustrated_ui','achievements_ui'):
            setattr(self.app,name,lambda name=name:self.calls.append(name))
        self.app.open_ui=lambda r:self.calls.append(r)
        self.ui=SceneUI(self.app)
        # Retain the real map's terrain function while selecting actual open ground.
        self.app.x,self.app.y=next(((x+.5)*64,(y+.5)*64)
            for y in range(self.app.map.height) for x in range(self.app.map.width)
            if not self.app.map.blocked((x+.5)*64,(y+.5)*64))

    def render(self):
        frame=Image.new('RGBA',(960,576))
        self.ui.render(frame)
        return frame

    def expand(self):
        self.ui.toggle('left')
        self.ui.groups['left']['clock']-=.21
        return self.render()

    def click(self,key):
        r=self.ui.hits[key]
        self.assertTrue(self.ui.click((r[0]+r[2])/2,(r[1]+r[3])/2))

    def test_closed_icons_have_no_invisible_hit_regions(self):
        self.render()
        self.assertFalse(set(self.ui.ride_buttons)&set(self.ui.hits))
        self.assertEqual([500001,500002,500003,500004,500005],list(self.ui.ride_buttons.values()))

    def test_opening_and_immediately_folding_never_opens_a_dialog(self):
        self.render()
        for _ in range(10):
            self.click('mainLeft_Button')
            self.render()
        self.assertEqual([],self.calls)
        self.assertEqual(0,self.ui.groups['left']['target'])

    def test_expanded_buttons_are_visible_not_transparent_hotspots(self):
        self.app.state.rides=[500001]
        closed=self.render()
        expanded=self.expand()
        for key in self.ui.ride_buttons:
            r=tuple(round(v) for v in self.ui.hits[key])
            self.assertIsNotNone(ImageChops.difference(closed,expanded).crop(r).getbbox())
        ROOT.joinpath('outputs/verification').mkdir(parents=True,exist_ok=True)
        expanded.save(ROOT/'outputs/verification/ride-menu-0.2.59.png')

    def test_select_owned_mount_folds_and_second_selection_dismounts(self):
        self.app.state.rides=[500001]
        self.expand();self.click('left_right_1_Button')
        self.assertEqual(500001,self.app.state.ride)
        self.assertEqual(0,self.ui.groups['left']['target'])
        self.assertNotIn('left_right_1_Button',self.ui.hits)
        self.expand();self.click('left_right_1_Button')
        self.assertEqual(0,self.app.state.ride)
        self.assertEqual([],self.calls)

    def test_unowned_description_is_once_and_stale_clicks_do_not_repeat(self):
        self.expand();self.click('left_right_1_Button')
        self.ui.action('left_right_1_Button')
        self.assertEqual(1,len(self.calls))
        p=self.calls[0].data['parameters']
        self.assertEqual(51,p['uiid'])
        self.assertEqual(DATA.tables['Ride']['500001']['des'],p['text'])
        self.ui.groups['left']['clock']-=.21
        self.render()
        self.assertNotIn('left_right_1_Button',self.ui.hits)

    def test_owned_invalid_terrain_uses_expiring_nonmodal_original_tip(self):
        self.app.state.rides=[500002]
        self.expand();self.click('left_right_2_Button')
        self.assertEqual([],self.calls)
        self.assertEqual(0,self.app.state.ride)
        self.assertEqual('该坐骑不适应此地形',self.ui.tip[0])
        frame=self.render();before=frame.copy()
        self.ui.render_tip(frame)
        self.assertIsNotNone(ImageChops.difference(frame,before).getbbox())
        self.assertEqual([],self.calls)
        self.ui.tip=(self.ui.tip[0],time.monotonic()-2.1)
        self.ui.render_tip(frame)
        self.assertIsNone(self.ui.tip)

    def test_dismount_on_static_sprite_is_rejected_without_modal(self):
        self.app.state.rides=[500003];self.app.state.ride=500003
        self.app.x,self.app.y=next(((x+.5)*64,(y+.5)*64)
            for y in range(self.app.map.height) for x in range(self.app.map.width)
            if self.app.map.sprite_blocked((x+.5)*64,(y+.5)*64))
        self.expand();self.click('left_right_3_Button')
        self.assertEqual(500003,self.app.state.ride)
        self.assertEqual('此处不能收回坐骑',self.ui.tip[0])
        self.assertEqual([],self.calls)

    def test_host_mount_entry_uses_same_original_hud(self):
        self.app.battle=None;self.app.runtime=SimpleNamespace(running=False)
        self.app.ui_open=False;self.app.scene_ui=self.ui
        NativeGame.mounts_ui(self.app)
        self.assertEqual(1,self.ui.groups['left']['target'])
        self.assertEqual([],self.calls)

    def test_both_ground_mounts_remain_ridden_after_moving_on_ground(self):
        self.app.state.rides=[500001,500005]
        mounts=Mounts(self.app.state)
        for key in self.app.state.rides:
            mounts.select(key,0,2)
            self.assertTrue(mounts.enter(0,2))
            self.assertEqual(key,self.app.state.ride)

    def test_original_disabled_map_tip_and_water_dismount(self):
        self.app.state.rides=[500003,500002]
        mounts=Mounts(self.app.state)
        with self.assertRaisesRegex(ValueError,'该坐骑不适应此地图'):
            mounts.select(500003,0,3)
        mounts.select(500002,2,2)
        with self.assertRaisesRegex(ValueError,'此处不能收回坐骑'):
            mounts.select(0,2,2)
        self.assertEqual(500002,self.app.state.ride)

if __name__=='__main__':unittest.main(verbosity=2)
