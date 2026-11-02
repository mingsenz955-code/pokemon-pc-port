"""NPC branch-task selection from the original task/icon dispatch rules.

PlotEventManager::process 0x2f7958 runs a matching plot trigger first, then
the NPC's current branch script, then its ordinary talk script. Target icons
precede giver icons (getCurrentBranchTaskItem 0x2e6e9c); within each group,
the comparator sorts task state descending and key ID ascending.
"""
from game_state import numbers


class BranchTasks:
    def __init__(self, state):
        self.state = state

    def unlocked(self, row):
        # BranchTaskItem prerequisite comparisons require ALL pairs. Single
        # values such as the original "0" or "78" have no pair to compare.
        for column, compare in (('conditions_mtask', self.state.main_matches),
                                ('conditions_btask', self.state.branch_matches)):
            tokens = str(row.get(column, '0')).split(',')
            if len(tokens) < 2:
                continue
            values = [int(v) for v in tokens]
            if len(values) > 1 and len(values) % 2:
                raise ValueError(f'Malformed original branch prerequisite: {row["keyId"]}')
            if any(not compare(key, status) for key, status in zip(values[::2], values[1::2])):
                return False
        return True

    def for_npc(self, npc_id):
        from task_icons import main_icon
        if main_icon(self.state, npc_id):
            return None
        candidates = []
        for key, row in self.state.tables.get('BranchTask', {}).items():
            status = int(self.state.branch_states.get(str(key), 2))
            if status == 1 and self.unlocked(row):
                status = 2
            if status == 2 and not self.unlocked(row):
                continue
            if status not in (2, 3, 4):
                continue
            if status == 3 and int(npc_id) in numbers(row.get('targetNpcs', '0')):
                candidates.append((0, -status, int(key)))
            column = 'dispatchNpcs' if status == 2 else 'submitNpcs'
            if int(npc_id) in numbers(row.get(column, '0')):
                candidates.append((1, -status, int(key)))
        return str(min(candidates)[2]) if candidates else None
