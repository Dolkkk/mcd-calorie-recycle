#!/usr/bin/env python3
"""逐店精修 v4：街道/建筑后缀分词 + 中文数字层剥离 + 环校验宽松线。只处理 anchor-fallback。"""
import json, math, os, re, time, urllib.parse, urllib.request

DATA = os.path.expanduser('~/mcd_data/data.json')
CACHE = os.path.expanduser('~/mcd_data/photon_cache2.json')
d = json.load(open(DATA, encoding='utf-8'))
cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}

def flush():
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)

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
            req = urllib.request.Request(url, headers={'User-Agent': 'mcd-geocode/4.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                cache[key] = json.loads(r.read())['features']
            flush(); time.sleep(0.3)
            return cache[key]
        except Exception as e:
            print(f'   retry {attempt+1} "{q[:28]}": {e}', flush=True); time.sleep(2)
    cache[key] = []; flush(); return []

SPLIT = re.compile(r'(?<=[路街道巷园里区中心广场大厦桥湖城店])')  # 在这些字后面断开
def segments(s):
    out = []
    for chunk in re.findall(r'[\u4e00-\u9fa5A-Za-z0-9]+', s):
        if len(chunk) <= 6:
            out.append(chunk)
        else:
            out.extend(p for p in SPLIT.split(chunk) if len(p) >= 2)
            out.append(chunk)          # 全串也试一把
    return out

for anchor, stores in d['stores_by_anchor'].items():
    ac = d['anchor_coords'][anchor]
    used = {tuple(s['coord']) for s in stores if s.get('coord_note', '').startswith('geo')}
    for s in stores:
        if not s.get('coord_note', '').startswith('anchor-fallback'):
            continue
        name, addr = s['storeName'], s['address']
        mcp_km = s.get('distance', 0) / 1000.0
        name_tok = re.sub(r'^麦当劳(北京)?', '', name)
        name_tok = re.sub(r'餐厅$', '', name_tok).strip()
        addr_land = re.sub(r'(地下|地上)?[Bb]?[一二三四五六七八九十百千\d]*层.*$', '', addr)
        addr_land = re.sub(r'麦当劳$', '', addr_land).strip()
        addr_land = re.sub(r'^.*?[区县](?=[\u4e00-\u9fa5]{2,})', '', addr_land)  # 去掉开头"宣武区"等
        parts = segments(name_tok) + segments(addr_land)
        uniq_q, seen = [], set()
        for p in parts + [f'麦当劳 {name_tok}']:
            q = f'{p} 北京'
            if q not in seen and len(p) >= 2:
                seen.add(q); uniq_q.append(q)

        cands = []
        for q in uniq_q[:8]:
            for f in photon(q):
                coord = tuple(f['geometry']['coordinates'][:2])
                if not (115.7 < coord[0] < 117.4 and 39.4 < coord[1] < 41.1):
                    continue
                p = f['properties']
                text = ' '.join(str(p.get(k, '')) for k in ('name', 'street', 'housenumber', 'district', 'city'))
                score = sum(1 for t in re.findall(r'[\u4e00-\u9fa5A-Za-z0-9]+', name + ' ' + addr) if len(t) >= 2 and t in text)
                diffm = abs(hav(ac, coord) - mcp_km) * 1000
                score += 2 if diffm <= 250 else (1 if diffm <= 600 else 0)
                score += 1 if hav(ac, coord) <= 1.8 else 0
                cands.append((score, -diffm, coord, q, round(diffm)))
        cands.sort(reverse=True)
        picked = None
        for sc, nd, coord, q, diffm in cands:
            ok = (sc >= 2 and diffm <= 900) or (sc >= 3 and diffm <= 1500)
            if ok and coord not in used:
                picked = (sc, coord, q, diffm); break
        if picked is None:
            for sc, nd, coord, q, diffm in cands:
                if (sc >= 2 and diffm <= 900) or (sc >= 3 and diffm <= 1500):
                    picked = (sc, coord, q, diffm); break
        if picked:
            sc, coord, q, diffm = picked
            s['coord'] = list(coord)
            s['coord_quality'] = float(sc)
            s['coord_note'] = f'geo4|{q[:18]}|diff={diffm}m'
            used.add(tuple(coord))
        json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"{anchor} | {name[:18]:20s} | {s.get('coord_note')} | {tuple(round(x,6) for x in s['coord'])}", flush=True)

uniq = len({tuple(s['coord']) for st in d['stores_by_anchor'].values() for s in st})
named = sum(1 for st in d['stores_by_anchor'].values() for s in st if s.get('coord_note','').startswith('geo'))
print(f'\n最终：精修 {named}/40 | 唯一坐标 {uniq}')
