#!/usr/bin/env python3
"""收尾手术：品牌词不作强匹配证据；海淀镇补查。"""
import json, math, os, re, time, urllib.parse, urllib.request

DATA = os.path.expanduser('~/mcd_data/data.json')
CACHE = os.path.expanduser('~/mcd_data/photon_cache2.json')
d = json.load(open(DATA, encoding='utf-8'))
cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}
STOP = {'麦当劳', '北京', '餐厅', '有限', '公司'}

def hav(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 2*6371*math.asin(math.sqrt(h))

def photon(q, limit=5):
    key = json.dumps({'q': q, 'limit': limit}, ensure_ascii=False)
    if key in cache:
        return cache[key]
    url = 'https://photon.komoot.io/api/?' + urllib.parse.urlencode({'q': q, 'limit': limit})
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'mcd-geocode/7.0'})
            with urllib.request.urlopen(req, timeout=25) as r:
                cache[key] = json.loads(r.read())['features']
            json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False); time.sleep(0.3)
            return cache[key]
        except Exception as e:
            print(f'   retry {attempt+1} "{q[:24]}": {e}', flush=True); time.sleep(2)
    return cache.get(key, [])

# 1. 复查所有 geo 挑选：强匹配只剩品牌词的 → 撤回
for anchor, stores in d['stores_by_anchor'].items():
    for s in stores:
        note = s.get('coord_note', '')
        if note.startswith('geo') and '|' in note:
            evidence = note.rsplit('|', 1)[-1]
            if evidence in STOP:
                s['coord_note'] = 'anchor-fallback(撤回:仅品牌词匹配)'
                print(f"撤回 {s['storeName'][:20]}（证据仅“{evidence}”）")

# 2. 海淀镇专案补查（上次网络超时错过）
s = next(x for st in d['stores_by_anchor'].values() for x in st if '海淀镇' in x['storeName'])
ac = d['anchor_coords']['北京-中关村']
mcp_km = s.get('distance', 0) / 1000.0
print(f"\n海淀镇专案：mcp环={mcp_km}km addr={s['address']}")
best = None
for q in ('海淀镇西大街 北京', '海淀区海淀镇 北京', '海淀镇 北京', '麦当劳 海淀镇 北京'):
    for f in photon(q):
        p = f['properties']
        coord = tuple(f['geometry']['coordinates'][:2])
        if not (115.7 < coord[0] < 117.4 and 39.4 < coord[1] < 41.1):
            continue
        text = ' '.join(str(p.get(k, '')) for k in ('name', 'street', 'housenumber', 'district', 'city'))
        strong = [t for t in re.findall(r'[\u4e00-\u9fa5]{3,}', s['storeName'] + ' ' + s['address'])
                  if t not in STOP and t in text]
        diffm = abs(hav(ac, coord) - mcp_km) * 1000
        print(f"  [{q[:12]}] {str(p.get('name'))[:16]} | {p.get('street','')} | strong={strong} | diff={diffm:.0f}m | {coord}")
        if strong and diffm <= 2500 and (best is None or diffm < best[1]):
            best = (coord, diffm, q, strong)
if best:
    s['coord'] = list(best[0])
    s['coord_quality'] = 6.0
    s['coord_note'] = f'geo7|{best[2][:14]}|diff={round(best[1])}m|{best[3][0]}'
    print(f"✅ 海淀镇采纳: {s['coord_note']}")
else:
    print("⚠️ 海淀镇无可靠候选，维持低精度标注")

json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
uniq = len({tuple(x['coord']) for st in d['stores_by_anchor'].values() for x in st})
named = sum(1 for st in d['stores_by_anchor'].values() for x in st if x.get('coord_note','').startswith('geo'))
low = [x['storeName'] for st in d['stores_by_anchor'].values() for x in st if not x.get('coord_note','').startswith('geo')]
print(f'\n收尾：可靠 {named}/40 | 唯一坐标 {uniq} | 低精度门店: {[n[:14] for n in low]}')
