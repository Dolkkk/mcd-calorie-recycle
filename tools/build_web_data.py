#!/usr/bin/env python3
"""生成网页数据包 data.js（内联进页面的营养/门店/图片数据）"""
import json, os

DATA = os.path.expanduser('~/mcd_data/data.json')
OUT = os.path.expanduser('~/mcd-calorie-recycle/data.js')
d = json.load(open(DATA))

foods = []
for f in d['foods']:
    foods.append({
        'n': f['productName'],
        'k': f['energyKcal'],
        'kj': f['energyKj'],
        'p': f.get('protein'), 'f': f.get('fat'), 'c': f.get('carbohydrate'),
        'img': f.get('image') or '',
    })

stores = []
for anchor, sts in d['stores_by_anchor'].items():
    for s in sts:
        stores.append({
            'n': s['storeName'], 'a': s['address'],
            'o': s.get('open'), 'cl': s.get('close'),
            'anchor': anchor, 'coord': s.get('coord'), 'q': s.get('coord_quality'),
        })

bundle = {'foods': foods, 'stores': stores, 'anchors': d.get('anchor_coords', {}),
          'generated': d['generated_at'], 'source': 'mcd-mcp'}
js = '/* 麦麦热量回收计划 - 构建期数据（来源：麦当劳中国 MCP）*/\nconst DATA = ' + json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + ';\n'
open(OUT, 'w').write(js)
print('foods:', len(foods), '| stores:', len(stores), '| bytes:', len(js))
print('with img:', sum(1 for f in foods if f['img']))
