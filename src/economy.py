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
        if store_limit_group(row):row['repeat']='0'
        for field in ('des', 'des2', 'name'):
            row[field] = gold_text(row.get(field, ''))
        if row.get('gotItemKid')=='700002':
            if int(row['gotCount'])==20:row['gotCount']='10'
            row['costMoneyType']=GOLD
            row['costCount']=str(int(row['gotCount'])*100000)
            row['des']=row['des2']=f"{row['costCount']}金币兑换{row['gotCount']}个勋章"


def store_limit_group(row):
    import json
    try:
        rewards=json.loads(row.get('items','[]'))
        if any(str(k)=='700001' and int(n)==80000 for k,n in rewards) and str(row.get('costCount')) in ('2000','20000'):
            return 'gold80000'
    except (ValueError,TypeError):pass
    return ''
