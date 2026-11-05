"""Original task hand-in costs; pet costs require an explicit UID selection."""
from collections import Counter
from game_state import numbers


class TaskCosts:
    def __init__(self, state, parameters):
        self.state = state
        branch = 'btask' in parameters
        self.key = str(parameters['btask'] if branch else state.main_task)
        self.token = ('branch:' if branch else 'main:')+self.key
        self.row = state.tables['BranchTask' if branch else 'MainTask'][self.key]
        self.items, self.pets = Counter(), Counter()
        for key, count in zip(numbers(self.row['costIds']), numbers(self.row['costCounts'])):
            if key and count:
                if count < 0:
                    raise ValueError('任务交付数量无效。')
                (self.pets if str(key) in state.tables['Pet'] else self.items)[str(key)] += count

    def receipt(self):
        return {'items': dict(self.items), 'pets': dict(self.pets)}

    def committed(self):
        return bool(self.items or self.pets) and self.state.activities.get('task_handovers', {}).get(self.token) == self.receipt()

    def mark_committed(self):
        if self.items or self.pets:
            self.state.activities.setdefault('task_handovers', {})[self.token] = self.receipt()

    def candidates(self, species):
        return [p for p in self.state.pets+self.state.bank if p.species == str(species) and not p.trial_id]

    def consume(self, selected):
        if self.committed():
            return  # Resume a saved post-consumption request without charging twice.
        selected = list(selected)
        if len(set(selected)) != len(selected):
            raise ValueError('不能重复选择同一只宠物。')
        chosen = [p for p in self.state.pets+self.state.bank if p.uid in selected and not p.trial_id]
        if len(chosen) != len(selected) or Counter(p.species for p in chosen) != self.pets:
            raise ValueError('请选择任务要求的宠物。')
        with self.state.transaction():
            self.state.consume(self.items.keys(), self.items.values())
            active = self.state.pets[min(max(0, self.state.active_pet), len(self.state.pets)-1)] if self.state.pets else None
            for team in (self.state.pets, self.state.bank):
                team[:] = [p for p in team if p.uid not in selected]
            self.state.active_pet = (self.state.pets.index(active) if active in self.state.pets else 0)
            self.mark_committed()
