#!/usr/bin/env python3
"""终版救援 v6：滑窗切词强匹配（3-6字窗口）。只处理 anchor-fallback。"""
import json, math, os, re, time, urllib.parse, urllib.request

DATA = os.path.expanduser('~/mcd_data/data.json')
CACHE = os.path.expanduser('~/mcd_data/photon_cache2.json')
d = json.load(open(DATA, encoding='utf-8'))
cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}

EXTRA = {
    '景辉街': ['阳光保险金融中心', '阳光金融中心', '景辉街33号院', '景辉街'],
    '望京街': ['望京西园四区', '望京西园'],
    '湖光北路': ['湖光北路', '湖光北街'],
    '南湖北一街': ['南湖北一街', '南湖中园', '望京东园'],
    '阜安西路': ['阜安西路'],
    '海淀镇': ['海淀镇', '海淀镇西大街'],
}

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
            req = urllib.request.Request(url, headers={'User-Agent': 'mcd-geocode/6.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                cache[key] = json.loads(r.read())['features']
            flush(); time.sleep(0.3)
            return cache[key]
        except Exception as e:
            print(f'   retry {attempt+1} "{q[:24]}": {e}', flush=True); time.sleep(2)
    cache[key] = []; flush(); return []

def windows(s):
    out = set()
    for run in re.findall(r'[\u4e00-\u9fa5A-Za-z0-9]+', s):
        for wlen in (3, 4, 5, 6):
            for i in range(0, len(run) - wlen + 1):
                out.add(run[i:i+wlen])
    return out

for anchor, stores in d['stores_by_anchor'].items():
    ac = d['anchor_coords'][anchor]
    used = {tuple(s['coord']) for s in stores if s.get('coord_note', '').startswith('geo')}
    for s in stores:
        if not s.get('coord_note', '').startswith('anchor-fallback'):
            continue
        name, addr = s['storeName'], s['address']
        mcp_km = s.get('distance', 0) / 1000.0
        extra = []
        for key, qs in EXTRA.items():
            if key in name:
                extra = qs
        name_tok = re.sub(r'^麦当劳(北京)?|餐厅$', '', name).strip()
        qs = [f'{q} 北京' for q in ([name_tok] + extra)] + [f'麦当劳 {name_tok} 北京']
        proper = windows(name + ' ' + addr)

        cands = []
        for q in dict.fromkeys(qs):
            for f in photon(q):
                coord = tuple(f['geometry']['coordinates'][:2])
                if not (115.7 < coord[0] < 117.4 and 39.4 < coord[1] < 41.1):
                    continue
                p = f['properties']
                text = ' '.join(str(p.get(k, '')) for k in ('name', 'street', 'housenumber', 'district', 'city'))
                strong = sorted({t for t in proper if t in text}, key=len, reverse=True)
                diffm = abs(hav(ac, coord) - mcp_km) * 1000
                sc = (2 if strong else 0) + (2 if diffm <= 250 else 1 if diffm <= 600 else 0) + (1 if hav(ac, coord) <= 1.8 else 0)
                cands.append((sc, diffm, coord, q, strong))
        cands.sort(key=lambda x: (-x[0], x[1]))
        picked = None
        for sc, diffm, coord, q, strong in cands:
            ok = (sc >= 3 and diffm <= 1200) or (strong and diffm <= 2500)
            if ok and coord not in used:
                picked = (sc, diffm, coord, q, strong); break
        if picked is None:
            for sc, diffm, coord, q, strong in cands:
                if (sc >= 3 and diffm <= 1200) or (strong and diffm <= 2500):
                    picked = (sc, diffm, coord, q, strong); break
        if picked:
            sc, diffm, coord, q, strong = picked
            s['coord'] = list(coord)
            s['coord_quality'] = float(sc)
            s['coord_note'] = f'geo6|{q[:14]}|diff={round(diffm)}m|{strong[0] if strong else ""}'
            used.add(tuple(coord))
        json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"{anchor} | {name[:18]:20s} | {s.get('coord_note')} | {tuple(round(x,6) for x in s['coord'])}", flush=True)

uniq = len({tuple(s['coord']) for st in d['stores_by_anchor'].values() for s in st})
named = sum(1 for st in d['stores_by_anchor'].values() for s in st if s.get('coord_note','').startswith('geo'))
print(f'\n最终：精修 {named}/40 | 唯一坐标 {uniq}')
