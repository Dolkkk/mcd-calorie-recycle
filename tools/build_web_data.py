#!/usr/bin/env python3
"""生成网页数据包 data.js（内联进页面的营养/门店/图片数据）
v2：门店来自全城撒网+距离环解算（solved_stores.json），营养/图片沿用 data.json"""
import json, os

DATA = os.path.expanduser('~/mcd_data/data.json')
SOLVED = os.path.expanduser('~/mcd_data/solved_stores.json')
OUT = os.path.expanduser('~/mcd-calorie-recycle/data.js')
d = json.load(open(DATA))
sol = json.load(open(SOLVED))

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
for s in sol['stores']:
    stores.append({
        'n': s['name'], 'a': s['addr'],
        'o': s.get('open'), 'cl': s.get('close'),
        'anchor': 'sweep', 'coord': s.get('coord'), 'q': s.get('resid_m'),
    })

# 老 8 锚点保留（页面商圈快捷按钮用）
anchors = {k: v for k, v in d.get('anchor_coords', {}).items()}

bundle = {'foods': foods, 'stores': stores, 'anchors': anchors,
          'generated': sol['generated_at'], 'source': 'mcd-mcp'}
js = '/* 麦麦热量回收计划 - 构建期数据（来源：麦当劳中国 MCP）*/\nconst DATA = ' + json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + ';\n'
open(OUT, 'w').write(js)
located = sum(1 for s in stores if s['coord'])
print('foods:', len(foods), '| stores:', len(stores), '| located:', located, '| bytes:', len(js))
print('with img:', sum(1 for f in foods if f['img']))
