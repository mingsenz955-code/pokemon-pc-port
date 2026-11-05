"""Recover only provably committed legacy story handovers, without a second cost."""
from task_costs import TaskCosts


def recover_legacy_handover(data, state):
    # pEvent503005's completed flag can only be reached through its cost step:
    # the "not enough pets" branch uses end without state=1. It ends by going
    # to exit 60301; pEvent603001 then submits task 131. Old passive inventory
    # refreshes reset state 4 -> 3 after consuming the five pets and dropped
    # that queued arrival. Do not infer a handover from mere catch history.
    if (state.main_task != 131 or 131 in state.completed_main
            or state.pending_runtime or state.events.get('503005') != 1
            or state.events.get('603001') == 1):
        return None
    row = state.tables['MainTask'].get('131', {})
    if (row.get('costIds'), row.get('costCounts'), row.get('nextTaskId')) != ('100093', '5', '132'):
        return None
    sequence = data.event('pEvent503005.json')
    if (sequence[-1].get('type') != 'tomap'
            or str(sequence[-1].get('parameters', {}).get('exit')) != '60301'
            or not any(s['type'] == 'costtaskitem' for s in sequence)):
        return None
    cost = TaskCosts(state, {'mtask':131})
    if cost.committed():
        return None
    cost.mark_committed()
    return {'event':'pEvent503005.json', 'index':len(sequence)-1, 'arrival_map':603}


def recover_missed_island_departure(data, state):
    """Finish task 155 if its one-shot area trigger was bypassed by sailing on.

    pEvent1501001 only fires on area 130101 (the Elens exit). A player who took
    another exit first can reach the Phantom Sea while task 155 is still at
    state 3. pEvent1501002 is the committed "two days later" handover and ends
    by submitting 155 at Phantom Island; replay only its final tomap/submit
    steps so the skipped area flag is never fabricated.
    """
    if (state.main_task != 155 or 155 in state.completed_main
            or state.main_state not in (3, 4) or state.map_id == 1301
            or state.pending_runtime
            or state.events.get('1301002') != 1
            or state.events.get('1501002') == 1):
        return None
    row = state.tables['MainTask'].get('155', {})
    if (row.get('conditionType'), row.get('conditions'), row.get('nextTaskId')) != ('1', '130101', '156'):
        return None
    sequence = data.event('pEvent1501002.json')
    if (sequence[-1].get('type') != 'submittask'
            or not any(s['type'] == 'tomap'
                       and str(s.get('parameters', {}).get('exit')) == '131102'
                       for s in sequence)):
        return None
    index = max(i for i, step in enumerate(sequence) if step['type'] == 'tomap')
    return {'event':'pEvent1501002.json', 'index':index, 'trigger_id':'1501002'}
