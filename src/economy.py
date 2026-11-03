"""Offline edition: original RMB prices are stored in fen, not yuan."""
import re

GOLD = '700001'
CASH = '700003'
GOLD_PER_YUAN = 1000
GOLD_PER_FEN = GOLD_PER_YUAN // 100
EVOLUTION_GOLD_COST = 5 * GOLD_PER_YUAN


def gold_text(value):
    return re.sub(r'(\d+(?:\.\d+)?)\s*元',
                  lambda m: f'{round(float(m[1])*GOLD_PER_YUAN)}金币', str(value))


def adapt_tables(tables):
    """Modify only the in-memory tables; keep recovered files untouched."""
    for row in tables['Store'].values():
        if row['costMoneyType'] == CASH:
            row['costMoneyType'] = GOLD
            row['costCount'] = str(int(row['costCount'])*GOLD_PER_FEN)
        for field in ('des', 'des2', 'name'):
            row[field] = gold_text(row.get(field, ''))
