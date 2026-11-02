"""Original DailyTask (每日任务) table, daily reset and claim logic.

The eight rows in ``DailyTask`` are fixed by the 1.20.4 table: seven normal
tasks and one meta task (key 1) that requires all seven to be submitted. The
table has no reward-on-login shortcut; the original TaskUI exposes a receive
button, so this module keeps completion and claiming separate.
"""
from __future__ import annotations

from datetime import date

from game_state import numbers


class DailyTasks:
    KEY = 'daily_tasks'
    # TaskConditionType / DailyTaskItem subclasses:
    # 3 catch, 5 fight, 4 talk, 10 purchase, 11 roulette, 12 cards, 13 race.
    ACTIONS = {
        'catch': '3',
        'fight': '2',
        'talk': '4',
        'purchase': '8',
        'roulette': '5',
        'cards_win': '6',
        'running_win': '7',
    }
    NORMAL_IDS = ('2', '3', '4', '5', '6', '7', '8')

    def __init__(self, state):
        self.state = state
        self.tables = state.tables

    def _today(self):
        return date.today().isoformat()

    def _entry(self, today=None):
        today = today or self._today()
        entry = self.state.activities.get(self.KEY)
        # Preserve today's claims when a clock correction moves backwards.
        if not isinstance(entry, dict) or not entry.get('date') or entry['date'] < today:
            entry = {'date': today, 'counters': {}, 'claimed': []}
            self.state.activities[self.KEY] = entry
        entry.setdefault('counters', {})
        entry.setdefault('claimed', [])
        return entry

    def refresh(self, today=None):
        return self._entry(today)

    def row(self, task_id):
        row = self.tables.get('DailyTask', {}).get(str(task_id))
        if not row:
            raise KeyError(f'原版 DailyTask 表没有任务 {task_id}')
        return row

    def required(self, task_id):
        values = numbers(self.row(task_id).get('counts'))
        return values[0] if values else 0

    def counter(self, task_id, today=None):
        return int(self._entry(today)['counters'].get(str(task_id), 0) or 0)

    def normal_completed(self, today=None):
        return sum(1 for task_id in self.NORMAL_IDS
                   if self.counter(task_id, today) >= self.required(task_id))

    def progress(self, task_id, today=None):
        if str(task_id) == '1':
            # DailyTaskItem::submitTask @ 0x2ff91c emits type 14 only on
            # submission; DTaskSubmit::process @ 0x2fe1c8 increments by one.
            # Ready-but-unclaimed tasks must not advance this counter.
            claimed = {str(key) for key in self._entry(today)['claimed']}
            return sum(key in claimed for key in self.NORMAL_IDS)
        return self.counter(task_id, today)

    def ready(self, task_id, today=None):
        return self.progress(task_id, today) >= self.required(task_id)

    def claimed(self, task_id, today=None):
        return str(task_id) in {str(v) for v in self._entry(today)['claimed']}

    def status(self, today=None):
        self.refresh(today)
        rows = []
        for task_id in sorted(self.tables['DailyTask'], key=int):
            row = self.row(task_id)
            rows.append({
                'id': str(task_id), 'name': row['name'], 'des': row['des'],
                'progress': self.progress(task_id, today), 'required': self.required(task_id),
                'ready': self.ready(task_id, today), 'claimed': self.claimed(task_id, today),
                'reward_ids': numbers(row.get('rewardIds')),
                'reward_counts': numbers(row.get('rewardCounts')),
            })
        return rows

    def record(self, action, amount=1, today=None):
        task_id = self.ACTIONS.get(action)
        if not task_id or 'DailyTask' not in self.tables:
            return None
        amount = int(amount)
        if amount <= 0:
            return None
        entry = self._entry(today)
        current = int(entry['counters'].get(task_id, 0) or 0)
        limit = self.required(task_id)
        entry['counters'][task_id] = min(limit, current+amount)
        return {'task_id': task_id, 'count': entry['counters'][task_id],
                'required': limit}

    def claim(self, task_id, today=None):
        self.refresh(today)
        task_id = str(task_id)
        row = self.row(task_id)
        if self.claimed(task_id, today):
            raise ValueError('这个每日任务今天已经领取过了。')
        if not self.ready(task_id, today):
            raise ValueError('每日任务尚未完成，不能领取。')
        ids = numbers(row.get('rewardIds'))
        counts = numbers(row.get('rewardCounts'))
        if len(ids) != len(counts):
            raise ValueError(f'每日任务 {task_id} 奖励表长度不一致。')
        with self.state.transaction():
            for item_id, count in zip(ids, counts):
                if count:
                    self.state.grant(str(item_id), count)
            self._entry(today)['claimed'].append(task_id)
        return {'task_id': task_id, 'rewards': [[str(i), int(c)] for i, c in zip(ids, counts)]}
