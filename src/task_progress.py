"""Original task condition counters (types 1–7), independent of presentation.

ARM references: MainTaskItem*::process, setReachCount, acceptTask and
PlayerDataManager::getDropItemCount. Higher branch types remain pending.
"""


def integers(value):
    return [int(v) for v in str(value).split(',') if v.strip()]


class TaskProgress:
    WIDTHS = {1: 1, 2: 4, 3: 3, 4: 1, 5: 4, 6: 1, 7: 1}
    EVENTS = {'area': 1, 'catch': 3, 'talk': 4, 'fight': 5, 'obstacle': 6, 'map': 7}

    def __init__(self, state):
        self.state = state

    def collection_count(self, condition):
        kind, identifier, level, unique = condition
        if kind in (2, 7):
            return self.state.count(identifier)
        if kind == 1:
            pets = [p for p in self.state.pets+self.state.bank
                    if (identifier == -1 or p.species == str(identifier))
                    and (level == -1 or p.level == level)]
            return len({p.species for p in pets}) if unique == 1 else len(pets)
        raise ValueError(f'Original collection kind {kind} is not implemented')

    def update(self, kind=None, *parameters):
        state = self.state
        tasks = [('main', str(state.main_task), state.main_state)]
        tasks.extend(('branch', key, status) for key, status in list(state.branch_states.items()))
        for category, key, status in tasks:
            if status not in (3, 4):
                continue
            row = state.tables['MainTask' if category == 'main' else 'BranchTask'].get(key)
            if not row:
                continue
            condition_type = int(row['conditionType'])
            # MainTaskItemTalk::acceptTask @ 0x300264 enters state 4
            # immediately; dialogue itself is guarded by the event script.
            if category == 'main' and condition_type == 4:
                state.main_state = 4
                continue
            width = self.WIDTHS.get(condition_type)
            if width is None:
                continue
            conditions, required = integers(row['conditions']), integers(row['counts'])
            if len(conditions) != width*len(required):
                raise ValueError(f'Malformed original {category} task {key} conditions')
            counter_key = f'{category}:{key}'
            counts = state.task_counts.setdefault(counter_key, [0]*len(required))
            if len(counts) != len(required):
                raise ValueError('Saved task counter length does not match original data')
            for index in range(len(required)):
                condition = conditions[index*width:(index+1)*width]
                if condition_type == 2:
                    counts[index] = self.collection_count(condition)
                elif status == 3 and self.EVENTS.get(kind) == condition_type:
                    if len(parameters) == width and all(expected == -1 or expected == actual
                                                       for expected, actual in zip(condition, parameters)):
                        counts[index] += 1
            results = [actual >= target for actual, target in zip(counts, required)]
            ready = any(results) if int(row.get('conditionAny', 0)) else all(results)
            updated = 4 if ready else 3
            if category == 'main':
                state.main_state = updated
            else:
                state.branch_states[key] = updated
