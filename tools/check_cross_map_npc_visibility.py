"""Native global NPC state, cross-village story and restored task hand-in."""
import json
from pathlib import Path
import check_single_window_flows as fixtures
import check_sunshine_quests as story_checks
from event_runtime import Request
from npc_visibility import value,migrate
import unittest

class CrossMapNpcChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown
    click=fixtures.SingleWindowChecks.click
    finish=story_checks.SunshineQuestChecks.finish

    def at_npc(self,identifier):
        a=self.app;actor=next(row for row in a.actors() if row[0]==identifier)
        a.x,a.y=actor[2],actor[3]+64

    def test_original_sally_moves_between_gyms_and_task_24_handover_continues(self):
        a=self.app;a.state.main_task,a.state.main_state=21,4
        a.state.events.update({'6201004':1,'203004':1})
        a.load_map(6201);self.at_npc('620101');a.interact('620101')
        self.assertEqual(a.runtime.file,'pEvent6201001.json');self.finish()
        self.assertEqual(a.state.main_task,22)
        self.assertFalse(value(a.state,6201,2,620101))
        a.load_map(5901,672,800)
        self.assertTrue(any(row[0]=='590103' for row in a.actors()))
        a.process_player_areas(force=True);a.drive()
        self.assertEqual(a.runtime.file,'pEvent5901003.json');self.finish()
        self.assertEqual(a.state.main_task,23)
        a.state.main_task,a.state.main_state=24,4
        a.state.events['5901004']=1
        first=a.state.add_generated_pet('100029',5)
        second=a.state.add_generated_pet('100029',6)
        self.at_npc('590103');a.interact('590103');self.finish_to_handover()
        before=a.state.count('700001')
        self.click('handin_pet_'+first.uid);self.click('confirm_Button');self.finish()
        self.assertNotIn(first.uid,[p.uid for p in a.state.pets+a.state.bank])
        self.assertIn(second.uid,[p.uid for p in a.state.pets+a.state.bank])
        self.assertEqual(a.state.completed_main.count(24),1)
        self.assertEqual(a.state.main_task,25)
        self.assertEqual(a.state.count('700001'),before+1000)
        self.assertTrue(a.save());self.assertTrue(a.restore())
        self.assertEqual(a.state.completed_main.count(24),1)
        self.assertEqual(a.state.count('700001'),before+1000)

    def finish_to_handover(self):
        a=self.app
        for _ in range(1000):
            self.assertFalse(a.runtime_error,a.runtime_error)
            if a.ui_open:return
            if a.display_request:a.interact()
            else:a.story_motion.advance(.1);a.advance_camera(.1);a.drive()
        self.fail('No original hand-in panel')

    def test_legacy_wrong_map_visibility_recovers_actor_and_persists(self):
        a=self.app;a.state.main_task,a.state.main_state=24,4
        a.state.visible={'6201:2:590103':True}
        a.state.presentation.pop('global_npc_visibility_version',None)
        a.state.events.update({'6201001':1,'5901003':1,'5901004':1})
        a.load_map(5901,736,576)
        self.assertFalse(any(row[0]=='590103' for row in a.actors()))
        self.assertTrue(a.save());self.assertTrue(a.restore())
        self.assertTrue(any(row[0]=='590103' for row in a.actors()))
        self.assertTrue(a.npc_motion.visible('590103'))
        audit=len(a.state.audit);migrate(a.state);self.assertEqual(len(a.state.audit),audit)
        self.assertTrue(a.save());self.assertTrue(a.restore())
        self.assertTrue(any(row[0]=='590103' for row in a.actors()))

    def test_visibility_migration_marker_survives_save(self):
        a=self.app;a.state.visible={'101:2:10109':False,'109:2:10109':True}
        a.state.presentation.pop('global_npc_visibility_version',None)
        self.assertTrue(a.save());self.assertTrue(a.restore())
        self.assertEqual(a.state.presentation['global_npc_visibility_version'],1)
        before=len([r for r in a.state.audit if r.get('repair')=='global-npc-visibility'])
        self.assertTrue(a.save());self.assertTrue(a.restore())
        after=len([r for r in a.state.audit if r.get('repair')=='global-npc-visibility'])
        self.assertEqual(before,after)

    def test_autosave_and_normal_close_preserve_progress_but_skip_battle(self):
        from unittest.mock import patch
        from game_state import GameState
        a=self.app;a.state.main_task,a.state.main_state=24,4
        a.root.after_cancel(a.autosave_job);a.autosave()
        loaded=GameState.load(a.data.tables,a.save_path)
        self.assertEqual(loaded.main_task,24)
        before=a.save_path.read_bytes();a.battle=object()
        a.root.after_cancel(a.autosave_job);a.autosave()
        self.assertEqual(a.save_path.read_bytes(),before)
        a.battle=None;a.state.main_task=25
        with patch.object(a.root,'destroy') as destroyed:
            a.close_game();destroyed.assert_called_once()
        self.assertEqual(GameState.load(a.data.tables,a.save_path).main_task,25)
        self.assertTrue(a.save_path.with_suffix('.json.bak').exists())

    def test_explicit_later_hide_and_chest_same_id_remain_independent(self):
        a=self.app;a.load_map(6201)
        for visible in (1,0,1):
            a.apply_visual(Request('spritevisible','test',1,{'parameters':{'spritetype':2,'spriteid':590103,'visible':visible}}))
            a.load_map(5901)
            self.assertEqual(any(row[0]=='590103' for row in a.actors()),bool(visible))
        a.load_map(5802)
        chest=[r for r in a.actors() if r[0]=='580201' and r[1]=='30001']
        a.apply_visual(Request('spritevisible','test',1,{'parameters':{'spritetype':2,'spriteid':580201,'visible':0}}))
        self.assertTrue(chest)
        self.assertTrue(any(r[0]=='580201' and r[1]=='30001' for r in a.actors()))
        self.assertFalse(any(r[0]=='580201' and r[1]!='30001' for r in a.actors()))

    def test_all_original_npc_visibility_commands_resolve_global_state(self):
        a=self.app;directory={};rows=[]
        for mid in a.data.tables['VillageMap']:
            world=a.data.load_map(mid)
            for obj in world.objects:
                if obj['group']=='spriteLayer' and obj.get('gid'):
                    sid=world.tile_properties(int(obj['gid'])).get('spriteId')
                    if sid and obj.get('name') and str(sid)!='30001':directory.setdefault(str(obj['name']),set()).add(str(mid))
        for path in (a.data.root/'events').glob('*.json'):
            if path.name=='pEventContents.json':continue
            for step in a.data.event(path.name):
                if step['type']!='spritevisible':continue
                commands=step['parameters'];commands=commands if isinstance(commands,list) else [commands]
                for command in commands:
                    if command.get('spritetype')!=2:continue
                    identifier=str(command['spriteid']);maps=sorted(directory.get(identifier,()))
                    a.apply_visual(Request('spritevisible',path.name,step['id'],{'parameters':command}))
                    for mid in maps:
                        self.assertEqual(value(a.state,mid,2,identifier),bool(command['visible']))
                    rows.append({'event':path.name,'step':step['id'],'npc':identifier,'maps':maps})
        self.assertGreater(len(rows),100)
        report=Path(__file__).resolve().parent.parent/'outputs/verification/npc-visibility-audit.json'
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':unittest.main(verbosity=2)
