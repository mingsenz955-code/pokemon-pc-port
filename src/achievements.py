"""Original Achievement table, with only locally verifiable conditions claimable.

The 1.20.4 table contains 142 rows and 23 different condition types.  This
module exposes all rows, but refuses to fabricate a progress value for a
condition type that the port does not track yet.  Claiming is atomic and only
possible when the matching action counter or GameState collection exists.
"""
from __future__ import annotations


class Achievements:
    SUPPORTED = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 22, 23, 24}
    COUNTERS = {3: ('caught_total', '野外捕获'),
                4: ('hatch_total', '孵化'),
                5: ('evolve_total', '进化'),
                7: ('ride_total', '骑乘'),
                23: ('save_total', '存档')}

    def __init__(self, state):
        self.state = state
        self.rows = state.tables.get('Achievement', {})

    @staticmethod
    def _ints(value):
        return [int(part) for part in str(value or '').split(',') if str(part).strip()]

    def claimed(self):
        return list(self.state.activities.get('achievements', []))

    def score(self):
        return sum(int(self.rows[key].get('score', 0))
                   for key in self.claimed() if key in self.rows)

    def progress(self, key):
        """Return (current, target, detail) or None when not verifiable."""
        row = self.rows.get(str(key))
        if not row:
            return None
        condition_type = int(row.get('conditionType', 0) or 0)
        target = int(row.get('count', 1) or 1)
        values = self._ints(row.get('conditions'))
        if condition_type == 2:
            if len(values) == 1:
                item_type = values[0]
                owned = {str(item) for item, count in self.state.inventory.items()
                         if int(count) > 0
                         and str(self.state.tables['Item'].get(str(item), {}).get('type', '')) == str(item_type)}
                return len(owned), target, f'已拥有 {len(owned)} 种 type={item_type} 道具'
            return None
        if condition_type == 6:
            if values:
                uses = self.state.activities.get('heal_items', {})
                current = sum(int(uses.get(str(item), 0)) for item in values)
                return current, target, f'已使用指定回复/飞越道具 {current} 次'
            return None
        if condition_type == 9:
            current = int(self.state.activities.get('oneshot_wins', 0))
            return current, target, f'一次攻击击败 {current} 次'
        if condition_type == 10:
            names = {'103': 'petrify', '111': 'sleep'}
            if values and str(values[0]) in names:
                applied = self.state.activities.get('status_applies', {})
                current = int(applied.get(names[str(values[0])], 0))
                return current, target, f'已施加 {current} / {target} 次'
            return None
        if condition_type == 18:
            # -1,<moneyType>,1 = total spent in any shop; the 5,-1,-1 rows
            # describe a separate mystery-shop counter that is not wired yet.
            if len(values) >= 2 and values[0] == -1:
                spent = self.state.activities.get('shop_spent', {})
                current = int(spent.get(str(values[1]), 0))
                return current, target, f'已消费 {current} / {target}'
            return None
        if condition_type == 19:
            # 1=main shop, 3=material shop, 4=scroll shop.
            if values:
                talks = self.state.activities.get('shop_talks', {})
                current = int(talks.get(str(values[0]), 0))
                return current, target, f'与店员对话 {current} / {target} 次'
            return None
        if condition_type == 20:
            if values:
                key = str(values[0])
                current = int(self.state.count(key))
                return current, target, f'银行格子上限 {current} / {target}'
            return None
        if condition_type == 24:
            if len(values) >= 2 and values[0] == 2:
                kind = values[1]
                species = {str(value) for value in self.state.encyclopedia}
                if kind == -1:
                    current = len(species)
                    return current, target, f'图鉴已记录 {current} 种宠物'
                current = sum(1 for value in species
                              if str(self.state.tables['Pet'].get(value, {}).get('kind', '')) == str(kind))
                return current, target, f'已获得 {current} 种 kind={kind} 宠物'
            return None
        if condition_type == 1:
            # The first collection family filters by one quality/rarity slot.
            if len(values) >= 4 and values[2] != -1 and values[0] == -1 and values[3] == -1 and values[4:] == [-1, -1, 0]:
                grade = values[2]
                current = sum(1 for pet in self.state.pets+self.state.bank
                              if int(getattr(pet, 'quality', 0)) == grade)
                return current, target, f'当前拥有品质 {grade} 的宠物 {current} 只'
            return None
        if condition_type == 11:
            if values and values[-1] == -1:
                current = int(self.state.activities.get('battle_wins', 0))
                return current, target, f'已取得 {current} 场战斗胜利'
            return None
        if condition_type in self.COUNTERS:
            counter, label = self.COUNTERS[condition_type]
            current = int(self.state.activities.get(counter, 0))
            return current, target, f'已{label} {current} 次'
        if condition_type == 8:
            current = len(self.state.bank)
            return current, target, f'银行当前存有 {current} 只宠物'
        if condition_type == 22:
            current = int(self.state.activities.get('play_seconds', 0))//60
            return current, target, f'游戏时间 {current} 分钟'
        if condition_type == 12:
            obstacle_type = values[0] if values else -1
            current = sum(1 for entry in self.state.removed_obstacles
                          if len(entry) > 3 and int(entry[3]) == obstacle_type)
            return current, target, f'已破坏 {current} 个 obsType={obstacle_type} 障碍'
        if condition_type == 13:
            current = int(self.state.activities.get('talk_total', 0))
            return current, target, f'已与 NPC 谈话 {current} 次'
        if condition_type == 14:
            current = len(self.state.activities.get('village_chests', []))
            return current, target, f'已开启 {current} 个村庄宝箱'
        if condition_type == 15:
            maps = set(values)
            visited = set(int(v) for v in self.state.visited_maps)
            current = len(maps & visited)
            return current, target, f'已到达 {current}/{len(maps)} 张目标地图'
        if condition_type == 17:
            current = len(self.state.completed_branch)
            return current, target, f'已完成 {current} 条支线'
        return None

    def status(self, key):
        key = str(key)
        row = self.rows.get(key)
        if not row:
            return 'missing'
        if key in self.claimed():
            return 'claimed'
        progress = self.progress(key)
        if progress is None:
            return 'unsupported'
        return 'ready' if progress[0] >= progress[1] else 'progress'

    def entry(self, key):
        key = str(key)
        row = self.rows[key]
        progress = self.progress(key)
        current, target = (progress[0], progress[1]) if progress else (None, int(row.get('count', 1) or 1))
        return {
            'id': key,
            'row': row,
            'name': row.get('name', key),
            'des': row.get('des', ''),
            'condition_type': int(row.get('conditionType', 0) or 0),
            'score': int(row.get('score', 0) or 0),
            'current': current,
            'target': target,
            'detail': progress[2] if progress else '',
            'status': self.status(key),
        }

    def entries(self, status=None):
        rows = [self.entry(key) for key in sorted(self.rows, key=lambda value: int(value))]
        if status == 'supported':
            rows = [row for row in rows if row['condition_type'] in self.SUPPORTED]
        elif status:
            rows = [row for row in rows if row['status'] == status]
        return rows

    def claim(self, key):
        key = str(key)
        row = self.rows.get(key)
        if not row:
            raise KeyError(f'没有原版成就 {key}')
        claimed = self.claimed()
        if key in claimed:
            raise ValueError('这个成就已经领取过了。')
        progress = self.progress(key)
        if progress is None:
            raise ValueError(f'原版成就条件类型 {row.get("conditionType")} 尚未接入，不能伪造完成。')
        current, target, _ = progress
        if current < target:
            raise ValueError(f'成就尚未完成：{current}/{target}')
        with self.state.transaction():
            reward_ids = self._ints(row.get('rewardIds'))
            reward_counts = self._ints(row.get('rewardCounts'))
            if len(reward_ids) != len(reward_counts):
                raise ValueError('原版成就奖励数组不匹配')
            for item_id, count in zip(reward_ids, reward_counts):
                self.state.grant(item_id, count)
            claimed.append(key)
            self.state.activities['achievements'] = claimed
        return {'id': key, 'score': int(row.get('score', 0) or 0),
                'rewards': list(zip(reward_ids, reward_counts))}