"""Original ContinuousLogin seven-day cumulative reward table.

The 1.20.4 table has seven rows.  PlayerDataManager stores
continuousLoginDays and loginTime; ContinuousLoginUILayer::getButtonRespond
grants the current row and raises LoginRewardReceivedEvent.
checkLoginInRewardCanReceived 0x32a618 requires a positive calendar-day
difference; it does not reset on a gap. loginRewardReceived 0x330fcc advances
the cumulative reward counter. Claim atomically, at most once per day.
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
        eligible = not last
        if last:
            try:
                gap = (datetime.date.fromisoformat(today)
                       - datetime.date.fromisoformat(last)).days
            except ValueError:
                gap = 0
            eligible = gap > 0
        day = entry['day']
        next_day = min(7, day+1) if day < 7 else 7
        return {
            'day': day,
            'next_day': next_day,
            'claimed_today': claimed_today,
            'complete': day >= 7,
            'reset': False,  # Compatibility with older host callers.
            'can_claim': eligible and day < 7,
            'today': today,
        }

    def claim(self, today=None):
        today = today or datetime.date.today().isoformat()
        status = self.status(today)
        if status['claimed_today']:
            raise ValueError('今天已经领取过连续登录奖励了。')
        if status['complete']:
            raise ValueError('连续登录七天奖励已经全部领取。')
        if not status['can_claim']:
            raise ValueError('尚未到下一个可领取奖励的日期。')
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
