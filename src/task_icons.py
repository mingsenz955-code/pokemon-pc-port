"""Original TaskIcon IDs and priority, separate from dialogue history.

Giver icons are 10+state (main) and 20+state (branch). Target icons are
19/29. Sources: addMainTaskIcon 0x2e71f4, addBranchTaskIcon 0x2e72a4,
showTaskIcon 0x2e70e8 and the corresponding task addIcons methods.
"""
from game_state import numbers
from branch_tasks import BranchTasks


def main_icon(state, npc_id):
    row = state.tables.get('MainTask', {}).get(str(state.main_task))
    status = int(state.main_state)
    if not row or status not in (2, 3, 4):
        return 0
    if status == 3 and int(npc_id) in numbers(row.get('targetNpcs', '0')):
        return 19
    column = 'dispatchNpcs' if status == 2 else 'submitNpcs'
    return 10+status if int(npc_id) in numbers(row.get(column, '0')) else 0


class TaskIcons:
    def __init__(self, state):
        self.state = state
        self._signature = None
        self._icons = {}

    def icons(self):
        state = self.state
        signature = (id(state.tables), state.main_task, state.main_state, tuple(sorted(state.branch_states.items())))
        if signature == self._signature:
            return self._icons
        candidates = {}
        def add(npc, priority, status, key, icon):
            if npc:
                candidates.setdefault(str(npc), []).append((priority, -status, int(key), icon))
        main = state.tables.get('MainTask', {}).get(str(state.main_task), {})
        status = int(state.main_state)
        if status in (2, 3, 4):
            column = 'dispatchNpcs' if status == 2 else 'submitNpcs'
            for npc in numbers(main.get(column, '0')):
                add(npc, 1, status, state.main_task, 10+status)
            if status == 3:
                for npc in numbers(main.get('targetNpcs', '0')):
                    add(npc, 0, status, state.main_task, 19)
        branches = BranchTasks(state)
        for key, row in state.tables.get('BranchTask', {}).items():
            status = int(state.branch_states.get(str(key), 2))
            if status == 1 and branches.unlocked(row):
                status = 2
            if status == 2 and not branches.unlocked(row):
                continue
            if status not in (2, 3, 4):
                continue
            column = 'dispatchNpcs' if status == 2 else 'submitNpcs'
            for npc in numbers(row.get(column, '0')):
                add(npc, 3, status, key, 20+status)
            if status == 3:
                for npc in numbers(row.get('targetNpcs', '0')):
                    add(npc, 2, status, key, 29)
        self._icons = {npc: min(choices)[3] for npc, choices in candidates.items()}
        self._signature = signature
        return self._icons

    def for_npc(self, npc_id):
        return self.icons().get(str(npc_id), 0)

    @staticmethod
    def bob(elapsed):
        # Native sequence: MoveBy(0.2, y=-4), MoveBy(0.2, y=+4), repeat.
        phase = (float(elapsed) % .4)/.2
        return 4*(phase if phase <= 1 else 2-phase)
