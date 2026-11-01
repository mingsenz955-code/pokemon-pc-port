"""Original RunningPet (赛宠嘉年华) betting/race rules, independent of Tk.

Evidence from the 1.20.4 ARM binary:
- RunningPetReadyUILayer::createUiLayer(int selected, float override) stores
  the selected pet and the per-race override; getWinnerIndex() rolls
  RandomHelper(1,100) and returns the selected pet when the roll is within the
  probability, otherwise a random different pet.
- Formula_GetRunningPetWinProbability(float) @ 0x2b5db4 computes
  1 / (1.2 + override / 3.0).
- RunningPetReadyUILayer::handleResult() settles
  int(bet * (override - 1)) on a win and -bet on a loss with medal 700008.
- leftButtonRespond/rightButtonRespond step the bet by one, wrapping to 10
  above the cap and to the cap below 10; getBetMaxMedalCount() caps at 9999.
- RunningPetUILayer::getWinnerRunTime() is 8.0 seconds; other runners use
  getRandomRunningPetRunTime(8.0), i.e. 1.01-1.30 times the winner time.
The host does not invent a different payout or a different medal.
"""
from __future__ import annotations

import random


class RunningPetGame:
    MEDAL = '700008'
    MIN_BET = 10
    MAX_BET = 9999
    WINNER_RUN_TIME = 8.0

    def __init__(self, state):
        self.state = state

    @property
    def rows(self):
        return list(self.state.tables.get('RunningPet', {}).values())

    def can_enter(self):
        return self.state.count(self.MEDAL) >= self.MIN_BET

    def max_bet(self):
        return min(self.state.count(self.MEDAL), self.MAX_BET)

    def contenders(self, rng=None):
        """getRandomRunningPetData + getBetOverride, four independent runners."""
        rng = rng or self.state.rng
        rows = self.rows
        if not rows:
            raise ValueError('原版 RunningPet 表为空。')
        result = []
        for index in range(4):
            row = rows[rng.randrange(len(rows))]
            result.append({
                'index': index,
                'id': str(row.get('keyId', '')),
                'name': row.get('name', ''),
                'filePath': row.get('filePath', ''),
                'des': row.get('des', ''),
                'override': rng.randint(15, 100) / 10.0,
            })
        return result

    def new_session(self, rng=None):
        if not self.can_enter():
            raise ValueError('赛宠报名至少需要 10 枚游戏奖牌。')
        session = {
            'contenders': self.contenders(rng),
            'selected': 0,
            'bet': self.MIN_BET,
            'settled': False,
            'winner': None,
            'delta': 0,
            'times': [],
            'started': None,
        }
        session['bet'] = min(session['bet'], self.max_bet())
        return session

    def select(self, session, index):
        index = int(index)
        if not 0 <= index < len(session['contenders']):
            raise ValueError('请选择 1–4 号赛宠。')
        session['selected'] = index

    def adjust_bet(self, session, delta):
        """Mirror left/rightButtonRespond's wrap behavior."""
        maximum = self.max_bet()
        bet = int(session['bet'])
        if delta > 0:
            bet += 1
            if bet > maximum:
                bet = self.MIN_BET
        elif delta < 0:
            bet -= 1
            if bet < self.MIN_BET:
                bet = maximum
        else:
            raise ValueError('押注只能增加或减少。')
        session['bet'] = max(self.MIN_BET, min(bet, maximum))
        return session['bet']

    @staticmethod
    def win_probability(override):
        """Formula_GetRunningPetWinProbability: 1 / (1.2 + override/3)."""
        return 1.0 / (1.2 + float(override) / 3.0)

    def winner_index(self, session, rng=None):
        rng = rng or self.state.rng
        selected = int(session['selected'])
        override = float(session['contenders'][selected]['override'])
        roll = rng.randint(1, 100)
        if roll <= self.win_probability(override) * 100.0:
            return selected
        while True:
            candidate = rng.randrange(4)
            if candidate != selected:
                return candidate

    def race_times(self, winner, rng=None):
        """Winner 8.0s; others use the original two-bound runtime formula.

        getRandomRunningPetRunTime(base):
          low  = RandomHelper(101,105)/100 * base
          high = RandomHelper(110,130)/100 * base
          low + (high-low) * canonical_random
        The low bound is 8.08s, so the preselected winner always arrives first.
        """
        rng = rng or self.state.rng
        times = []
        for index in range(4):
            if index == winner:
                times.append(self.WINNER_RUN_TIME)
                continue
            low = rng.randint(101, 105) / 100.0 * self.WINNER_RUN_TIME
            high = rng.randint(110, 130) / 100.0 * self.WINNER_RUN_TIME
            times.append(low + (high - low) * rng.random())
        return times

    def settle(self, session, rng=None):
        """Settle once using the original medal delta and preserve race stats."""
        if session.get('settled'):
            raise ValueError('这场赛跑已经结算过了。')
        rng = rng or self.state.rng
        selected = int(session['selected'])
        winner = self.winner_index(session, rng)
        override = float(session['contenders'][selected]['override'])
        bet = int(session['bet'])
        if bet < self.MIN_BET or bet > self.max_bet():
            raise ValueError('押注奖牌数不在当前可用范围内。')
        session['winner'] = winner
        session['times'] = self.race_times(winner, rng)
        if winner == selected:
            # __fixsfsi(int(bet * (override - 1.0))) in handleResult.
            delta = int(bet * (override - 1.0))
            with self.state.transaction():
                self.state.grant(self.MEDAL, delta)
        else:
            delta = -bet
            with self.state.transaction():
                self.state.consume([self.MEDAL], [bet])
        session['delta'] = delta
        session['settled'] = True
        stats = self.state.activities.setdefault(
            'running_pet', {'races': 0, 'wins': 0, 'streak': 0, 'best_streak': 0})
        stats['races'] = int(stats.get('races', 0)) + 1
        if winner == selected:
            stats['wins'] = int(stats.get('wins', 0)) + 1
            stats['streak'] = int(stats.get('streak', 0)) + 1
            stats['best_streak'] = max(int(stats.get('best_streak', 0)), stats['streak'])
        else:
            stats['streak'] = 0
        return {
            'winner': winner,
            'selected': selected,
            'won': winner == selected,
            'delta': delta,
            'medals': self.state.count(self.MEDAL),
            'override': override,
            'bet': bet,
        }

    def result_text(self, session):
        selected = int(session['selected'])
        winner = int(session.get('winner', selected))
        contender = session['contenders'][selected]
        if winner == selected:
            return (f'获胜了！{contender["name"]} 获得冠军；'
                    f'押注 {session["bet"]}，赢得 {session["delta"]} 奖牌。')
        winner_name = session['contenders'][winner]['name']
        return (f'失败！{winner_name} 获得冠军；'
                f'押注 {session["bet"]} 失去 {abs(session["delta"])} 奖牌。')