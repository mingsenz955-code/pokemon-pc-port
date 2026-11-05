"""X capture controller sequences, callbacks and actual render regressions."""
import copy
import json
import struct
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from PIL import Image,ImageDraw
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
from check_restoration_097 import host
OUT=ROOT/'outputs/verification/0.2.100'
OUT.mkdir(parents=True,exist_ok=True)

def capture(success):
    ui=host()
    ui.battle.events=[{'type':'catch_attempt'}]+([{'type':'caught','name':ui.battle.enemy_active.pet.species}] if success else [])
    ui._capture_events()
    if success:
        ui.battle.result='caught'
        ui.battle.caught_pet=copy.deepcopy(ui.battle.enemy_active.pet)
    return ui

def native_sequence(name):
    with (ROOT/'research/apk-x-2.10.9/lib/armeabi/libcocos2dcpp.so').open('rb') as stream:
        elf=ELFFile(stream)
        symbol=next(s for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name==name)
        segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=symbol['st_value']<s['p_vaddr']+s['p_filesz'])
        data=segment.data()[symbol['st_value']-segment['p_vaddr']:][:symbol['st_size']]
        return tuple(v for v in struct.unpack('<'+'I'*(len(data)//4),data) if v)

class CaptureChecks(unittest.TestCase):
    def test_real_failed_roll_keeps_enemy_attack_after_capture(self):
        ui=host()
        ui.battle.can_catch=True
        with patch.object(ui.battle,'capture_chance',return_value=0):
            ui.battle.choose_item('220004')
        self.assertTrue(any(e['type']=='catch_failed' for e in ui.battle.events))
        ui._after_action()
        self.assertEqual('capture',ui.anim['kind'])
        self.assertTrue(ui.anim_queue)
        self.assertTrue(any(a['side']=='enemy' for a in ui.anim_queue))
        ui.advance(seconds=9)
        self.assertEqual('capture',ui.anim['kind'])
        ui.advance(seconds=.31)
        self.assertNotEqual('capture',ui.anim['kind'])
    def test_fallback_assets_contain_the_same_capture_clips(self):
        from original_data import OriginalData
        data=OriginalData(ROOT/'original-1.20.4')
        _,source=data.armature_source('kaichong')
        names={m['name'] for m in source['animation_data'][0]['mov_data']}
        for n in native_sequence('catch_success_seq')+native_sequence('catch_failed_seq'):
            self.assertIn(f'Animation{n}',names)

    def test_both_sequences_match_supplied_binary_not_single_clip(self):
        for success in (True,False):
            ui=capture(success)
            plan=ui.anim['capture_plan']
            actual=tuple(int(name.removeprefix('Animation')) for name,_,_ in plan['segments'])
            self.assertEqual(native_sequence('catch_success_seq' if success else 'catch_failed_seq'),actual)
            self.assertEqual('Animation7',ui.anim['capture_clip'])
            self.assertEqual(484 if success else 558,plan['response'])
            self.assertEqual(220,plan['in'])
            self.assertEqual(None if success else 433,plan['out'])
    def test_every_segment_boundary_uses_local_authored_frame(self):
        ui=capture(False)
        plan=ui.anim['capture_plan']
        for name,start,duration in plan['segments']:
            self.assertEqual((name,0),ui._capture_segment(plan,start))
            self.assertEqual((name,duration-1),ui._capture_segment(plan,start+duration-.01))
    def test_enemy_remains_before_in_then_shrinks_and_hides(self):
        ui=capture(True)
        anchor=ui.pet_positions['enemy']
        self.assertEqual((1,anchor,1),ui._capture_pose(0,anchor))
        self.assertEqual(1,ui._capture_pose(219,anchor)[0])
        self.assertAlmostEqual(.55,ui._capture_pose(328,anchor)[0])
        self.assertEqual(0,ui._capture_pose(346,anchor)[0])
        self.assertEqual(0,ui._capture_pose(483,anchor)[0])
    def test_failed_capture_restores_original_pet_scale_alpha_position(self):
        ui=capture(False)
        anchor=ui.pet_positions['enemy']
        self.assertEqual(0,ui._capture_pose(432,anchor)[0])
        scale,point,alpha=ui._capture_pose(433,anchor)
        self.assertAlmostEqual(.1,scale)
        self.assertEqual((480,288),point)
        self.assertAlmostEqual(20/255,alpha)
        self.assertEqual((1,anchor,1),ui._capture_pose(469,anchor))
    def test_visual_shake_never_changes_battle_random_state(self):
        ui=capture(False)
        before=ui.battle.rng.getstate()
        for frame in range(220,310):ui._capture_pose(frame,ui.pet_positions['enemy'])
        self.assertEqual(before,ui.battle.rng.getstate())
    def test_large_delta_plays_each_authored_sound_once_and_cry_at_response(self):
        ui=capture(True)
        played=[]
        ui.effect_audio=SimpleNamespace(play=played.append)
        cry=ui.anim.get('response_sound')
        ui.advance(seconds=80/60)
        self.assertEqual(['6029','6029'],played)
        self.assertEqual(0,ui.result_age)
        ui.advance(seconds=300/60)
        self.assertEqual(['6029','6029','6030'],played)
        self.assertIsNotNone(ui.anim)
        ui.advance(seconds=104/60+.0001)
        self.assertIsNone(ui.anim)
        if cry:self.assertEqual(cry,played[-1])
        count=len(played)
        ui.advance(seconds=.2)
        self.assertEqual(count,len(played))
        self.assertGreater(ui.result_age,0)
    def test_failure_blocks_queued_enemy_action_until_native_response(self):
        ui=capture(False)
        ui.anim_queue.append({'kind':'attack','side':'enemy','age':0,'duration':26,'damages':[]})
        ui.advance(seconds=557/60)
        self.assertEqual('capture',ui.anim['kind'])
        ui.advance(seconds=2/60)
        self.assertEqual('attack',ui.anim['kind'])
        self.assertAlmostEqual(25/60,ui.anim['age'])
    def test_render_all_capture_phases(self):
        for success in (True,False):
            ui=capture(success)
            for frame in (0,20,75,219,250,310,328,360,400,433,450,468,480):
                ui.anim['age']=frame*25/60
                ui.frame=None
                image=ui.render()
                self.assertEqual((960,576),image.size)

def visuals():
    frames=(20,75,220,310,328,360,400,433,450,480)
    sheet=Image.new('RGB',(480*5,312*4),'#20252c')
    draw=ImageDraw.Draw(sheet)
    for row,success in enumerate((True,False)):
        ui=capture(success)
        for index,frame in enumerate(frames):
            ui.anim['age']=frame*25/60;ui.frame=None
            image=ui.render().convert('RGB').resize((480,288))
            x=(index%5)*480;y=(row*2+index//5)*312
            sheet.paste(image,(x,y))
            draw.text((x+8,y+290),f'{"success" if success else "failed"} / frame {frame}',fill='white')
    sheet.save(OUT/'capture-phases.jpg',quality=88)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CaptureChecks))
    (OUT/'capture-regressions.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},indent=2),encoding='utf-8')
    if result.wasSuccessful():visuals()
    sys.exit(not result.wasSuccessful())
