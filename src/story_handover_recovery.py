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
