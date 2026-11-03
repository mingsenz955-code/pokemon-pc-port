"""Keep water traversal independent from removable rocks and trees."""
import unittest
import check_single_window_flows as fixtures
from mounts import Mounts

class RideObstacleChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown

    def rock(self,ride=500002):
        a=self.app;a.state.rides=[500001,500002,500003,500004,500005];a.state.ride=ride
        a.load_map(202)
        for (tx,ty),kind in a.map.obstacles.items():
            if kind!=2:continue
            for dx,dy in [(0,1),(-1,0),(1,0),(0,-1)]:
                x,y=(tx+dx+.5)*64,(ty+dy+.5)*64
                if not a.map.blocked(x,y):
                    a.x,a.y=x,y
                    return (tx+.5)*64,(ty+.5)*64
        self.fail('No original seaside rock with a walkable neighbour')

    def test_lapras_cannot_enter_or_erase_original_rock(self):
        a=self.app;x,y=self.rock();before=(a.x,a.y);removed=list(a.state.removed_obstacles)
        a.move_to(x,y)
        self.assertEqual((a.x,a.y),before)
        self.assertEqual(a.state.removed_obstacles,removed)
        self.assertEqual(a.map.obstacle_at(x,y),2)
        self.assertEqual(a.state.ride,500002)

    def test_owned_lapras_does_not_auto_board_a_rock(self):
        a=self.app;x,y=self.rock(0);before=(a.x,a.y)
        a.move_to(x,y)
        self.assertEqual((a.x,a.y),before)
        self.assertEqual(a.state.ride,0)

    def test_water_auto_board_still_works(self):
        a=self.app;self.rock(0);a.load_map(201);m=Mounts(a.state)
        for ty in range(a.map.height):
            for tx in range(a.map.width):
                x,y=(tx+.5)*64,(ty+.5)*64
                if a.map.terrain_at(x,y)==2 and not a.map.obstacle_at(x,y) and not a.map.blocked(x,y,m):
                    a.move_to(x,y)
                    self.assertEqual((a.x,a.y),(x,y));self.assertEqual(a.state.ride,500002)
                    return
        self.fail('No original sea water found')

    def test_correct_mount_breaks_rock_once_and_flight_does_not_break(self):
        a=self.app;x,y=self.rock(500005);m=Mounts(a.state)
        self.assertTrue(a.map.blocked(x,y,m))
        self.assertFalse(a.map.route_blocked(x,y,m))
        a.move_to(x,y)
        self.assertEqual((a.x,a.y),(x,y));self.assertIsNone(a.map.obstacle_at(x,y))
        count=len(a.state.removed_obstacles);a.move_to(x,y)
        self.assertEqual(len(a.state.removed_obstacles),count)
        a.state.removed_obstacles=[];x,y=self.rock(500003)
        a.move_to(x,y)
        self.assertEqual((a.x,a.y),(x,y));self.assertEqual(a.map.obstacle_at(x,y),2)
        self.assertFalse(a.state.removed_obstacles)

    def test_all_five_mounts_apply_their_own_obstacle_abilities(self):
        a=self.app
        for ride in (500001,500002,500003,500004,500005):
            for kind in (1,2):
                with self.subTest(ride=ride,obstacle=kind):
                    a.state.removed_obstacles=[];self.rock(ride)
                    tx,ty=next(tile for tile,k in a.map.obstacles.items() if k==kind
                               and a.map.terrain_at((tile[0]+.5)*64,(tile[1]+.5)*64)==0
                               and not a.map.sprite_blocked((tile[0]+.5)*64,(tile[1]+.5)*64))
                    x,y=(tx+.5)*64,(ty+.5)*64;before=(a.x,a.y)
                    a.move_to(x,y)
                    breaks=(ride==500001 and kind==1 or ride==500005 and kind==2)
                    allowed=breaks or ride==500003
                    self.assertEqual((a.x,a.y)==(x,y),allowed)
                    self.assertEqual(a.map.obstacle_at(x,y) is None,breaks)
                    self.assertEqual(len(a.state.removed_obstacles),int(breaks))

    def test_click_route_for_lapras_avoids_rock(self):
        a=self.app;x,y=self.rock()
        a.guide.start_click(x,y)
        for _ in range(600):
            if not a.guide.active:break
            a.guide.step(.03)
        self.assertNotEqual((int(a.x//64),int(a.y//64)),(int(x//64),int(y//64)))
        self.assertEqual(a.map.obstacle_at(x,y),2)

    def test_old_save_inside_rock_is_moved_out_without_destroying_it(self):
        a=self.app;x,y=self.rock();a.x,a.y=x,y
        a.state.presentation['sprite_collision_version']=2
        inventory=dict(a.state.inventory)
        self.assertTrue(a.save());self.assertTrue(a.restore())
        self.assertNotEqual((a.x,a.y),(x,y))
        self.assertFalse(a.map.blocked(a.x,a.y,Mounts(a.state)))
        self.assertEqual(a.map.obstacle_at(x,y),2)
        self.assertEqual(a.state.inventory,inventory)
        self.assertTrue(any(e.get('repair')=='legacy-player-inside-obstacle' for e in a.state.audit))

    def test_all_original_obstacles_block_water_mount_independently_of_terrain(self):
        a=self.app;a.state.rides=[500002];a.state.ride=500002;m=Mounts(a.state);count=0
        for mid in a.data.tables['VillageMap']:
            world=a.data.load_map(mid)
            for (tx,ty),kind in world.obstacles.items():
                count+=1;x,y=(tx+.5)*world.tw,(ty+.5)*world.th
                self.assertTrue(world.blocked(x,y,m),(mid,tx,ty,kind))
        self.assertGreater(count,10000)

if __name__=='__main__':unittest.main(verbosity=2)
