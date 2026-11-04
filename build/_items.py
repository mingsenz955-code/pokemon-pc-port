import json
d = json.load(open('original-1.20.4/tables.json', encoding='utf-8'))
for key in ['Item','Money']:
    print('='*20, key)
    for k, v in d[key].items():
        text = json.dumps(v, ensure_ascii=False)
        if any(w in text for w in ['捕捉','捕获','球','胶囊','笼']):
            print(k, text)
print('='*20, 'PetItem all')
for k, v in d['PetItem'].items():
    print(k, json.dumps(v, ensure_ascii=False))
print('='*20, 'Item sample 230007')
for k in ['230007','230003','230005','230009']:
    print(k, json.dumps(d['Item'].get(k), ensure_ascii=False))