"""Treasure-map hunt recovered from the 1.20.4 tables and ARM symbols.

Evidence used here:
  * TreasureDataManager::initData / PlayerDataManager::addTreasure
  * PlayerDataManager::getTreasure / removeTreasure / treasureGiveUp
  * TreasureMapUILayer::useButtonRespond (requires itemId from the active
    Treasure row before sending the search event)
  * TChestPos.pos, TChest.itemIds/probabilitys/itemCounts, VillageChest

The map purchase price, currency, clue row, candidate chest positions and
chest loot all come from the original tables.  A purchased map grants the
row's itemId/itemCount (in 1.20.4 this is three magnifiers 220007), matching
the layout's "当前拥有个数" text.  Using a magnifier consumes one and reveals
the randomly chosen candidate position from Treasure.chestPoss.  The revealed
chest is then a normal map actor; opening it rolls one row from TChest.

There is no original TChest key-cost column.  The separate ChestItem table
(210001 + key 240001) belongs to the wild "宝箱" item, so this module does not
invent a key charge for map treasure.
"""
from __future__ import annotations

from game_state import numbers


class TreasureHunt:
    def __init__(self, state):
        self.state = state

    @property
    def rows(self):
        return self.state.tables.get('Treasure', {})

    def entries(self):
        return self.state.activities.setdefault('treasure_maps', [])

    def active(self):
        return next((e for e in self.entries() if not e.get('opened')), None)

    def visible_on(self, map_id):
        return [e for e in self.entries()
                if not e.get('opened') and e.get('revealed')
                and str(e.get('map_id')) == str(map_id)]

    def _resolve_map(self, name):
        for key, row in self.state.tables.get('VillageMap', {}).items():
            if str(row.get('name')) == str(name):
                return str(key)
        raise ValueError(f'原版 VillageMap 找不到宝藏线索地图：{name}')

    def _choose_position(self, row):
        positions = []
        for value in numbers(str(row.get('chestPoss', '')).replace('，', ',')):
            key = str(value)
            if key in self.state.tables.get('TChestPos', {}):
                positions.append(key)
        if not positions:
            raise ValueError('原版 Treasure.chestPoss 没有有效宝箱坐标')
        return str(self.state.rng.choice(positions))

    def buy(self, treasure_id):
        """Buy a clue map, grant its bundled magnifiers and hide one chest."""
        treasure_id = str(treasure_id)
        row = self.rows.get(treasure_id)
        if not row:
            raise ValueError('没有这个原版藏宝图。')
        if any(e.get('id') == treasure_id and not e.get('opened')
               for e in self.entries()):
            raise ValueError('这张藏宝图已经在进行中。')
        with self.state.transaction():
            money = str(row.get('moneyType', '0'))
            price = int(row.get('price', 0) or 0)
            if money != '0' and price:
                self.state.consume([money], [price])
            item_id = str(row.get('itemId', '0'))
            item_count = int(row.get('itemCount', 0) or 0)
            if item_id != '0' and item_count:
                self.state.grant(item_id, item_count)
            pos_id = self._choose_position(row)
            pos = self.state.tables['TChestPos'][pos_id]
            x, y = (int(part) for part in str(pos['pos']).split(','))
            chest_ids = [str(v) for v in numbers(str(row.get('chestIds', '')))]
            chest_id = str(self.state.rng.choice(chest_ids)) if chest_ids else '1'
            entry = {
                'id': treasure_id,
                'name': str(row.get('name', '')),
                'map_id': self._resolve_map(row.get('name', '')),
                'pos_id': pos_id,
                'x': x * 64 + 32,
                'y': y * 64 + 32,
                'chest_id': chest_id,
                'revealed': False,
                'opened': False,
            }
            self.entries().append(entry)
        return entry

    def use_magnifier(self, pos_id=None):
        """Consume one magnifier and reveal the active chest on the map."""
        entry = self.active()
        if not entry:
            raise ValueError('当前没有藏宝图。')
        if pos_id is not None and str(entry.get('pos_id')) != str(pos_id):
            raise ValueError('这张藏宝图不是这个宝箱。')
        if entry.get('revealed'):
            raise ValueError('宝藏已经显现，请直接去地图寻找。')
        with self.state.transaction():
            self.state.consume(['220007'], [1])
            entry['revealed'] = True
        return entry

    def open(self, pos_id):
        """Open a revealed map chest and roll one TChest reward row."""
        entry = next((e for e in self.entries()
                      if str(e.get('pos_id')) == str(pos_id)
                      and not e.get('opened')), None)
        if not entry:
            raise ValueError('这个宝藏不存在或已经打开。')
        if not entry.get('revealed'):
            raise ValueError('宝藏还没有显现，请先使用放大镜。')
        row = self.state.tables.get('TChest', {}).get(str(entry.get('chest_id')))
        if not row:
            raise ValueError('原版 TChest 表缺少这个宝箱。')
        ids = [str(v) for v in numbers(row.get('itemIds', ''))]
        counts = [int(v) for v in numbers(row.get('itemCounts', ''))]
        weights = [int(v) for v in numbers(row.get('probabilitys', ''))]
        if not ids or len(ids) != len(counts) or len(ids) != len(weights):
            raise ValueError('原版 TChest 奖励列不完整。')
        pick = self.state.rng.choices(range(len(ids)), weights=weights, k=1)[0]
        item_id, count = ids[pick], counts[pick]
        with self.state.transaction():
            self.state.grant(item_id, count)
            entry['opened'] = True
            self.entries().remove(entry)
        return item_id, count

    def give_up(self, pos_id=None):
        entry = self.active()
        if not entry:
            raise ValueError('当前没有藏宝图。')
        if pos_id is not None and str(entry.get('pos_id')) != str(pos_id):
            raise ValueError('这张藏宝图不是这个宝藏。')
        with self.state.transaction():
            self.entries().remove(entry)
        return entry

    def clue(self, row):
        chests = self.state.tables.get('TChest', {})
        names = []
        for key in numbers(str(row.get('chestIds', ''))):
            chest = chests.get(str(key))
            if chest:
                names.append(str(chest.get('name', key)))
        return {'text': str(row.get('des', '')),
                'map': str(row.get('name', '')),
                'chests': names,
                'price': int(row.get('price', 0) or 0),
                'money': str(row.get('moneyType', '0'))}