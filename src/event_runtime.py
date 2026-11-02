"""Resumable, data-driven interpreter for the original event format.

Presentation, battles and user choices yield typed requests. A request must be
completed by the native host; recognizing it never means the mechanic is done.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from game_state import numbers


class PendingMechanic(RuntimeError):
    pass


@dataclass
class Request:
    kind: str
    event: str
    step: int
    data: dict


class EventRuntime:
    PRESENTATION = {'toplace', 'face', 'toface', 'spritevisible', 'tempnpc', 'screenmove',
                    'screen', 'screenclose', 'screenflash', 'areamapmove', 'button',
                    'tapscreen', 'mainuivisible', 'addteachnode', 'openui', 'closeui',
                    'trialride', 'save', 'tomap'}
    STATE_COMMANDS = {'giveitem', 'eventstate', 'taskstate', 'submittask', 'costtaskitem',
                      'function', 'init', 'iarenastate', 'goto', 'end'}
    INTERACTIVE = {'talk', 'aside', 'airtalk', 'fight', 'fightover', 'accepttask', 'wait'}

    def __init__(self, data, state):
        self.data, self.state = data, state
        self.triggers = data.event('pEventContents.json')
        self.file, self.sequence, self.index = '', [], 0
        self.pending = None
        self.active_trigger = None
        self.queue = []
        self.battle_result = None
        self.save_event = True
        self.trigger_npc_id = 0

    @property
    def running(self):
        return bool(self.file)

    @staticmethod
    def pairs(values):
        if values and len(values) % 2:
            raise ValueError('Malformed original condition pair array')
        return list(zip(values[::2], values[1::2]))

    def matches(self, content):
        if not content.get('repeat', 0) and self.state.events.get(str(content['id']), 0):
            return False
        event_pairs = self.pairs(content.get('conditions_event', []))
        if any(int(self.state.events.get(str(k), 0)) != int(v) for k, v in event_pairs):
            return False
        # Original compareMainTaskConditions/compareBranchTaskConditions use ANY
        # task pair; compareEventConditions requires ALL event pairs.
        main = self.pairs(content.get('conditions_mtask', []))
        branch = self.pairs(content.get('conditions_btask', []))
        return ((not main or any(self.state.main_matches(k, v) for k, v in main)) and
                (not branch or any(self.state.branch_matches(k, v) for k, v in branch)))

    def notify(self, kind, **parameters):
        notification = {'kind': kind, 'parameters': parameters}
        if self.running:
            if notification not in self.queue:
                self.queue.append(notification)
            self.persist()
            return False
        for trigger in self.triggers:
            if trigger['type'] != kind or not self.matches(trigger):
                continue
            if any(not (kind == 'fightover' and k == 'petid' and int(v) == -1)
                   and str(parameters.get(k)) != str(v)
                   for k, v in trigger['conditions_add'].items()):
                continue
            self.start(f'pEvent{trigger["id"]}.json', trigger,
                       npc_id=parameters.get('npcid') if kind == 'talk' else None)
            return True
        if kind == 'talk':
            from branch_tasks import BranchTasks
            key = BranchTasks(self.state).for_npc(parameters['npcid'])
            if key is not None:
                self.start(f'pEventBTask{key}.json', npc_id=parameters['npcid'])
                return True
        return False

    def start(self, filename, trigger=None, *, npc_id=None):
        if self.running:
            raise RuntimeError('Cannot replace a running original event')
        if filename == 'pEventContents.json':
            raise ValueError('Trigger definitions are not executable event steps')
        sequence = self.data.event(filename)
        ids = [step['id'] for step in sequence]
        if len(ids) != len(set(ids)):
            raise ValueError(f'Duplicate step IDs in {filename}')
        self.file, self.sequence, self.index = filename, sequence, 0
        self.pending, self.active_trigger, self.battle_result = None, trigger, None
        self.trigger_npc_id = int(npc_id or (trigger or {}).get('conditions_add', {}).get('npcid', 0))
        self.save_event = True
        self.persist()

    def flush_queue(self):
        """Deliver notifications received while another event owned the runtime."""
        while self.queue and not self.running:
            notification = self.queue.pop(0)
            self.notify(notification['kind'], **notification['parameters'])
        self.persist()

    def jump(self, identifier):
        self.index = next((i for i, step in enumerate(self.sequence) if int(step['id']) == int(identifier)), -1)
        if self.index < 0:
            raise ValueError(f'Missing original jump destination {identifier} in {self.file}')

    def branch_matches(self, condition):
        checks = []
        state = int(condition.get('state', 1))
        if 'mtask' in condition:
            checks.append(self.state.main_matches(condition['mtask'], state))
        if 'btask' in condition:
            checks.append(self.state.branch_matches(condition['btask'], state))
        if 'npcfight' in condition:
            checks.append(int(self.state.npc_fights.get(str(condition['npcfight']), 0)) == state)
        if 'initid' in condition:
            checks.append(self.state.starter_id == int(condition['initid']))
        if 'ride' in condition:
            checks.append((int(condition['ride']) in self.state.rides) == bool(state))
        if 'event' in condition:
            checks.append(int(self.state.events.get(str(condition['event']), 0)) == state)
        if 'iarenaid' in condition:
            checks.append(int(self.state.arenas.get(str(condition['iarenaid']), 0)) == state)
        if 'npcid' in condition or 'npcId' in condition:
            # compareTriggerNpcId 0x2f7282 compares the NPC that initiated the
            # conversation. This selector does not inspect "state" or wins.
            checks.append(self.trigger_npc_id == int(condition.get('npcid', condition.get('npcId'))))
        return all(checks)

    def next(self):
        if self.pending:
            return self.pending
        budget = 0
        while self.running:
            budget += 1
            if budget > 2000:
                raise RuntimeError('Original event exceeded instruction budget; possible invalid branch loop')
            if self.index >= len(self.sequence):
                self.finish()
                continue
            step = self.sequence[self.index]
            kind, parameter = step['type'], step.get('parameters', {})
            if kind not in self.PRESENTATION | self.STATE_COMMANDS | self.INTERACTIVE:
                raise PendingMechanic(f'Unknown original command {kind}')
            if kind == 'fightover':
                if self.battle_result is None:
                    self.pending = Request('battleover', self.file, int(step['id']),
                                           copy.deepcopy(step))
                    self.persist()
                    return self.pending
                key = 'win' if self.battle_result == 'win' else 'lose'
                target = parameter.get(key)
                if target is None:
                    raise ValueError(f'Original fightover is missing {key} destination')
                self.battle_result = None
                self.index += 1
                self.jump(target)
                self.persist()
                continue
            if kind in self.PRESENTATION or kind in {'talk', 'aside', 'airtalk', 'fight',
                                                      'accepttask', 'wait'}:
                self.pending = Request(kind, self.file, int(step['id']), copy.deepcopy(step))
                self.persist()
                return self.pending
            # Mutating instructions advance only after successful completion.
            target = None
            if kind == 'giveitem':
                rows = parameter if isinstance(parameter, list) else [parameter]
                for row in rows:
                    if not any(str(row['itemid']) in self.state.tables[table] for table in ('Pet', 'Item', 'Money')):
                        raise ValueError(f'Unknown reward {row["itemid"]}')
                self.state.grant_many([row['itemid'] for row in rows],
                                      [row['itemcount'] for row in rows])
            elif kind == 'eventstate':
                for row in parameter if isinstance(parameter, list) else [parameter]:
                    self.state.events[str(row['eventid'])] = int(row['state'])
            elif kind == 'taskstate':
                if 'mtask' in parameter and int(parameter['mtask']) == self.state.main_task:
                    self.state.main_state = int(parameter['state'])
                elif 'btask' in parameter:
                    self.state.branch_states[str(parameter['btask'])] = int(parameter['state'])
            elif kind == 'submittask':
                # Original mtask is a nonzero flag; the handler submits the
                # current task, not that numeric ID (e.g. pEvent101005 uses 5
                # while the current task is 6). Branch IDs remain explicit.
                branch = 'btask' in parameter
                self.state.submit_task(parameter['btask'] if branch else self.state.main_task, branch)
            elif kind == 'costtaskitem':
                table = 'BranchTask' if 'btask' in parameter else 'MainTask'
                task = self.state.tables[table][str(parameter.get('btask', parameter.get('mtask')))]
                self.state.consume(numbers(task['costIds']), numbers(task['costCounts']))
            elif kind == 'function':
                rows = parameter if isinstance(parameter, list) else [parameter]
                for row in rows:
                    self.state.functions[str(row['id'])] = int(row['state'])
            elif kind == 'init':
                self.state.initialize(parameter['id'])
            elif kind == 'iarenastate':
                self.state.arenas[str(parameter['iarenaid'])] = int(parameter['state'])
            elif kind == 'goto':
                choices = parameter if isinstance(parameter, list) else [parameter]
                for condition in choices:
                    if self.branch_matches(condition):
                        target = condition['id']
                        break
            elif kind == 'end':
                # PlotEventItemEnd::begin -> eventForceEnd(state). Unlike natural
                # EOF, an explicit end without state=1 does not mark completion.
                self.save_event = int(parameter.get('state', 0)) == 1
                self.finish()
                continue
            self.index += 1
            if target is not None:
                self.jump(target)
            self.persist()
        return None

    def resume(self, result=None):
        if not self.pending:
            raise RuntimeError('No original event request is waiting')
        request = self.pending
        parameter = request.data.get('parameters', {})
        target = None
        if request.kind == 'fight':
            if result == 'start':
                self.battle_result = None
            elif result in ['win', 'lose', 'escape']:
                self.battle_result = result
            elif result in [False, 'no'] and 'no' in parameter:
                target = parameter.get('no')
            else:
                raise ValueError('A real battle outcome is required')
        elif request.kind == 'battleover':
            if result not in ['win', 'lose', 'escape']:
                raise ValueError('A real battle outcome is required')
            self.battle_result = result
            key = 'win' if result == 'win' else 'lose'
            target = parameter.get(key)
            if target is None:
                raise ValueError(f'Original fightover is missing {key} destination')
        elif request.kind in ('openui', 'closeui'):
            # The original closeui instruction carries no/yes step targets.
            # The host records the player's actual confirmation choice.
            if result in ('yes', 'no'):
                target = parameter.get(result)
        elif request.kind == 'accepttask':
            if type(result) is not bool:
                raise ValueError('A real player choice is required')
            target = parameter.get('yes' if result else 'no')
            if result:
                self.state.branch_states[str(parameter['btask'])] = 3
        self.pending = None
        self.index += 1
        if target is not None:
            self.jump(target)
        self.persist()

    def finish(self):
        if self.file and self.active_trigger and self.save_event:
            self.state.events[str(self.active_trigger['id'])] = 1
        if self.active_trigger and self.active_trigger.get('ending'):
            self.state.story_ending = True
        self.file, self.sequence, self.index = '', [], 0
        self.pending, self.active_trigger = None, None
        self.trigger_npc_id = 0
        queued, self.queue = self.queue, []
        self.persist()
        for index, event in enumerate(queued):
            if self.notify(event['kind'], **event['parameters']):
                self.queue.extend(queued[index+1:])
                break
        self.persist()

    def persist(self):
        self.state.pending_runtime = self.snapshot() if self.running else None

    def snapshot(self):
        return {'file': self.file, 'index': self.index, 'trigger': self.active_trigger,
                'trigger_npc_id': self.trigger_npc_id,
                'queue': copy.deepcopy(self.queue), 'battle_result': self.battle_result,
                'save_event': self.save_event,
                'pending': copy.deepcopy(self.pending.__dict__) if self.pending else None}

    def restore(self, snapshot):
        if not snapshot:
            return
        self.start(snapshot['file'], snapshot['trigger'])
        self.index = int(snapshot['index'])
        if not 0 <= self.index <= len(self.sequence):
            raise ValueError('Invalid saved event position')
        self.queue = copy.deepcopy(snapshot['queue'])
        self.battle_result = snapshot['battle_result']
        self.save_event = snapshot['save_event']
        self.trigger_npc_id = int(snapshot.get('trigger_npc_id', self.trigger_npc_id))
        self.pending = Request(**snapshot['pending']) if snapshot['pending'] else None
        self.persist()
