"""Original ContinuousLogin seven-day reward table and consecutive-day rules.

The 1.20.4 table has seven rows.  PlayerDataManager stores
continuousLoginDays and loginTime; ContinuousLoginUILayer::getButtonRespond
grants the current row and raises LoginRewardReceivedEvent.  The host models a
missed calendar day as a reset to day one, claims atomically, and never grants
the same day twice.
"""
from __future__ import annotations

import datetime


class ContinuousLogin:
    KEY = 'continuous_login'

    def __init__(self, state):
        self.state = state

    def rewards(self):
        return [row for _, row in sorted(
            self.state.tables.get('ContinuousLogin', {}).items(),
            key=lambda item: int(item[0]))]

    def _entry(self):
        entry = self.state.activities.setdefault(self.KEY, {'day': 0, 'last': ''})
        entry['day'] = int(entry.get('day', 0) or 0)
        return entry

    def status(self, today=None):
        today = today or datetime.date.today().isoformat()
        entry = self._entry()
        last = entry.get('last', '')
        claimed_today = bool(last == today)
        reset = False
        if last and not claimed_today:
            try:
                gap = (datetime.date.fromisoformat(today)
                       - datetime.date.fromisoformat(last)).days
            except ValueError:
                gap = 0
            if gap > 1:
                reset = True
        day = 0 if reset else entry['day']
        next_day = min(7, day+1) if day < 7 else 7
        return {
            'day': day,
            'next_day': next_day,
            'claimed_today': claimed_today,
            'complete': day >= 7,
            'reset': reset,
            'today': today,
        }

    def claim(self, today=None):
        today = today or datetime.date.today().isoformat()
        status = self.status(today)
        if status['claimed_today']:
            raise ValueError('今天已经领取过连续登录奖励了。')
        if status['complete']:
            raise ValueError('连续登录七天奖励已经全部领取。')
        entry = self._entry()
        day = status['day'] + 1
        row = self.state.tables['ContinuousLogin'].get(str(day))
        if not row:
            raise ValueError(f'原版 ContinuousLogin 缺少第 {day} 天。')
        reward, count = str(row['rewardKid']), int(row['rewardCount'])
        with self.state.transaction():
            self.state.grant(reward, count)
            entry['day'] = day
            entry['last'] = today
        return {'day': day, 'reward': reward, 'count': count, 'row': row}