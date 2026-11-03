import unittest,time
from PIL import Image,ImageChops
from types import SimpleNamespace
import check_single_window_flows as fixtures
from check_service_page_lifecycle import ServiceChecks
from mounts import Mounts

class PurchaseMountChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown
    open=fixtures.SingleWindowChecks.open
    click=fixtures.SingleWindowChecks.click
    enter_service=ServiceChecks.enter_service

    def test_purchase_toast_has_actual_quantity_without_advancing_clerk(self):
        for mid,oid in [(5802,'580201'),(5803,'580302'),(5804,'580401')]:
            with self.subTest(npc=oid):
                a=self.enter_service(mid,oid)
                a.state.inventory.update({'700001':10000000,'700002':10000000})
                pending,index=a.runtime.pending,a.runtime.index
                self.click('shop_goods_0/Layer/root_Panel/buy_Button')
                table=a.ui_parameters['table'];key=a.ui_parameters['key'];row=a.data.tables[table][key]
                self.click('right_Button');self.click('right_Button')
                balance=a.state.count(row['moneyType']);count=a.state.count(row['goodsKid'])
                self.click('confirm_Button')
                self.assertIn(row['name'],a.purchase_notice[0]);self.assertIn('×'+str(3*int(row.get('gotCount',1))),a.purchase_notice[0])
                self.assertEqual(a.state.count(row['moneyType']),balance-int(row['price'])*3)
                self.assertEqual(a.state.count(row['goodsKid']),count+3*int(row.get('gotCount',1)))
                self.assertIs(a.runtime.pending,pending);self.assertEqual(a.runtime.index,index)
                frame=a.ui_base_layer.copy();before=frame.tobytes();a.paint_purchase_notice(frame)
                self.assertNotEqual(frame.tobytes(),before)
                a.purchase_notice=(a.purchase_notice[0],time.monotonic()-1.1)
                frame=a.ui_base_layer.copy();a.paint_purchase_notice(frame)
                self.assertEqual(frame.tobytes(),a.ui_base_layer.tobytes());self.assertIsNone(a.purchase_notice)
                self.click('shop_goods_0/Layer/root_Panel/buy_Button');self.click('cancel_Button')
                self.assertIsNone(a.purchase_notice)
                self.click('shop_goods_0/Layer/root_Panel/buy_Button')
                a.state.inventory[row['moneyType']]=0;self.click('confirm_Button')
                self.assertIsNone(a.purchase_notice)

    def test_real_hud_mount_click_changes_visible_image_and_movement_keeps_mount(self):
        a=self.app;a.load_map(109,1312,1184);a.state.rides=[500003]
        before=a.player_image('standdown')
        def tap(key):
            r=a.scene_ui.hits[key];a.on_click(SimpleNamespace(x=(r[0]+r[2])/2,y=(r[1]+r[3])/2))
        a.scene_ui.render(Image.new('RGBA',(960,576)));tap('mainLeft_Button')
        a.scene_ui.groups['left']['clock']-=.3;a.scene_ui.render(Image.new('RGBA',(960,576)))
        tap('left_right_3_Button');self.assertEqual(a.state.ride,500003)
        mounted=a.player_image('standdown');self.assertNotEqual(before.size,mounted.size)
        expected=a.data.armature('zq6','standdown',int(a.scene_animation_time*60))
        self.assertEqual(mounted.tobytes(),expected.tobytes())
        a.move_to(a.x+1,a.y);self.assertEqual(a.state.ride,500003)
        a.player_walking=False
        a.scene_ui.groups['left'].update(value=1,start=1,target=1,clock=0)
        a.scene_ui.render(Image.new('RGBA',(960,576)));tap('left_right_3_Button')
        self.assertEqual(a.state.ride,0)
        self.assertEqual(a.player_image('standdown').size,before.size)

    def test_all_mount_models_directions_and_walk_animations_are_used(self):
        a=self.app;a.state.rides=[int(k) for k in a.data.tables['Ride']]
        a.scene_animation_time=.2
        for row in a.data.tables['Ride'].values():
            with self.subTest(ride=row['keyId']):
                Mounts(a.state).select(row['keyId'],Mounts.terrains(row)[0],2)
                for walking in (False,True):
                    a.player_walking=walking
                    for face in ['standdown','standup','standleft','standright']:
                        clip=face.replace('stand','walk') if walking else face
                        clip=clip.replace('right','left')
                        expected=a.data.armature(row['filePath'],clip,12)
                        actual=a.player_image(face)
                        if face.endswith('right'):
                            self.assertEqual(actual.info['origin'],(expected.width-expected.info['origin'][0],expected.info['origin'][1]))
                            expected=expected.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                        self.assertEqual(actual.tobytes(),expected.tobytes())

if __name__=='__main__':unittest.main(verbosity=2)
