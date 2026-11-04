import sys, json, traceback
sys.path.insert(0, 'src')
from original_data import OriginalData
from game_state import GameState
from event_runtime import EventRuntime, PendingMechanic
from battle import make_npc_battle

data = OriginalData('original-1.20.4')
state = GameState(data.tables, 20240607)
runtime = EventRuntime(data, state)
if not runtime.notify('tomap', map=7401):
    runtime.start('pEvent7401001.json')
battles = 0
for step in range(4000):
    try:
        request = runtime.next()
    except Exception as e:
        print('ERROR', runtime.file, runtime.index, type(e).__name__, e)
        traceback.print_exc()
        break
    if not request:
        print('END', runtime.file, runtime.index, 'events', state.events, 'main', state.main_task, state.main_state)
        runtime.flush_queue()
        if not runtime.running:
            try:
                m = data.load_map(str(state.map_id))
                for obj in m.objects:
                    if obj['group'] != 'eventLayer':
                        continue
                    try:
                        area = int(obj['name'])
                    except ValueError:
                        continue
                    if runtime.notify('toarea', area=area):
                        break
            except Exception as error:
                print('  area scan failed', error)
        if runtime.running:
            print('  -> next event', runtime.file)
            continue
        if state.map_id == 101 and state.main_task == 2:
            state.map_id = 5801
            state.main_state = 4
            print('  -> entered lab 5801')
        if state.map_id == 5801:
            npcs = (580104, 580101) if state.main_task == 3 and state.main_state == 3 else (580101, 580104)
            for npc in npcs:
                if runtime.notify('talk', npcid=npc):
                    break
                if runtime.notify('talk', npcid=npc):
                    break
            if runtime.running:
                print('  -> next event', runtime.file)
                continue
        if state.map_id == 5807:
            if runtime.notify('talk', npcid=580701):
                print('  -> next event', runtime.file)
                continue
        break
    kind = request.kind
    params = request.data.get('parameters', {})
    text = request.data.get('text') or '\n'.join(request.data.get('texts', [])) or ''
    if kind in ('talk', 'aside', 'airtalk', 'button', 'tapscreen'):
        print(step, kind, request.data.get('id'), text[:80].replace('\n', ' / '))
        runtime.resume()
    elif kind == 'fight':
        npcid = params.get('npcid')
        battle = make_npc_battle(data.tables, state.pets, npcid, state.rng)
        print(step, 'FIGHT', npcid, [(u.name, u.pet.level) for u in battle.enemy])
        for _ in range(60):
            if battle.result:
                break
            battle.choose_skill(1)
        print('   result', battle.result, 'rounds', battle.round)
        if battle.result == 'win':
            battle.apply_rewards(state)
        runtime.resume('win' if battle.result == 'win' else 'lose')
        battles += 1
    elif kind == 'battleover':
        print(step, 'BATTLEOVER pending without result')
        runtime.resume('win')
    elif kind == 'accepttask':
        print(step, 'ACCEPT', params.get('btask'))
        runtime.resume(True)
    elif kind == 'openui':
        print(step, 'OPENUI', params.get('uiid'), params)
        if int(params.get('uiid', 0)) == 7:
            key = int(params.get('par1', 1))
            state.add_preset(str(key))
            state.initialization = key
            state.main_state = 4
            print('   chose starter', key, state.pets[-1].species)
        runtime.resume()
    elif kind == 'closeui':
        print(step, 'CLOSEUI', params.get('uiid'))
        runtime.resume()
    elif kind == 'wait':
        print(step, 'WAIT', params.get('type'), params)
        runtime.resume()
    elif kind == 'tomap':
        exit_id = str(params.get('exit'))
        mid = next((k for k, row in data.tables['VillageMap'].items()
                    if exit_id in row['exitIds'].split(',')), None)
        print(step, 'TOMAP', exit_id, '->', mid, data.tables['VillageMap'].get(str(mid), {}).get('name'))
        if mid:
            state.map_id = int(mid)
            runtime.notify('tomap', map=int(mid))
        runtime.resume()
    else:
        if kind not in ('toplace', 'face', 'toface', 'spritevisible', 'tempnpc',
                        'screenmove', 'screen', 'screenclose', 'screenflash',
                        'areamapmove', 'mainuivisible', 'addteachnode', 'trialride', 'save'):
            print(step, 'UNHANDLED', kind, params)
        runtime.resume()
print('battles', battles, 'pets', [(p.species, p.level) for p in state.pets],
      'inventory', state.inventory)