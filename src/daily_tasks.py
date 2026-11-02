"""Offline DailyTask counters/claims from the original eight table rows.

Original handlers: BuyItem 0x2fe094, CardLegend 0x2fe100, PetRun 0x2fe164;
TaskUILayer::receiveButtonRespond 0x3bda74 only submits daily tasks.
"""
from datetime import datetime, timedelta, timezone
from game_state import numbers


def prerequisites(state, row):
    for column, compare in [('conditions_mtask', state.main_matches),
                            ('conditions_btask', state.branch_matches)]:
        values = numbers(row.get(column, '0'))
        if values == [0] or not values:
            continue
        if len(values) % 2:
            raise ValueError('Invalid original task prerequisite pairs')
        if not all(compare(key, status) for key, status in zip(values[::2], values[1::2])):
            return False
    return True


class DailyTasks:
    WIDTHS = {3: 3, 4: 1, 5: 4, 10: 1, 11: 1, 12: 1, 13: 1, 14: 1}
    EVENTS = {'catch': 3, 'talk': 4, 'fight': 5, 'buy': 10, 'roulette': 11,
              'cards': 12, 'race': 13, 'daily_submit': 14}

    def __init__(self, state):
        self.state = state

    def refresh(self, now=None):
        state = self.state
        date = (now or datetime.now(timezone(timedelta(hours=8)))).date().isoformat()
        current = state.activities.get('daily_tasks')
        # A backward clock change must not reopen already claimed tasks.
        if current is None or date > current['day']:
            current = {'day': date, 'states': {}, 'counts': {}}
            state.activities['daily_tasks'] = current
        for key, row in state.tables.get('DailyTask', {}).items():
            if key not in current['states'] or current['states'][key] in (1, 2):
                current['states'][key] = 3 if prerequisites(state, row) else 1
                current['counts'].setdefault(key, [0]*len(numbers(row['counts'])))
        return current

    def update(self, kind=None, *parameters, amount=1, now=None):
        if not self.state.tables.get('DailyTask'):
            return
        current = self.refresh(now)
        for key, row in self.state.tables['DailyTask'].items():
            if current['states'][key] != 3:
                continue
            condition_type = int(row['conditionType'])
            if condition_type != self.EVENTS.get(kind):
                continue
            width = self.WIDTHS.get(condition_type)
            if width is None:
                continue
            conditions, required = numbers(row['conditions']), numbers(row['counts'])
            if len(conditions) != width*len(required):
                raise ValueError(f'Malformed original DailyTask {key}')
            counts = current['counts'][key]
            for index, target in enumerate(required):
                expected = conditions[index*width:(index+1)*width]
                if len(parameters) == width and all(a == -1 or a == b for a, b in zip(expected, parameters)):
                    counts[index] = min(target, counts[index]+amount)
            checks = [a >= b for a, b in zip(counts, required)]
            if (any(checks) if int(row.get('conditionAny', 0)) else all(checks)):
                current['states'][key] = 4

    def claim(self, key, now=None):
        key = str(key)
        with self.state.transaction():
            current = self.refresh(now)
            if current['states'].get(key) != 4:
                raise ValueError('每日任务尚未完成或已领取奖励。')
            row = self.state.tables['DailyTask'][key]
            self.state.consume(numbers(row['costIds']), numbers(row['costCounts']))
            self.state.grant_many(numbers(row['rewardIds']), numbers(row['rewardCounts']))
            current['states'][key] = 5
            self.update('daily_submit', int(key), now=now)
        return list(zip(numbers(row['rewardIds']), numbers(row['rewardCounts'])))
