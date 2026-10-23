#!/usr/bin/env python3
"""构建期地理编码 v2：Photon 搜地标 + 麦当劳 POI，用 MCP distance 校验匹配
坐标系：WGS-84（与浏览器 GPS / OSRM 一致）
"""
import json, urllib.request, urllib.parse, time, os, math, re

DATA = os.path.expanduser('~/mcd_data/data.json')
d = json.load(open(DATA))
UA = {'User-Agent': 'mcd-calorie-recycle/0.1 (contest demo)'}
CACHE_PATH = os.path.expanduser('~/mcd_data/photon_cache.json')
cache = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}

def photon(**params):
    key = json.dumps(params, sort_keys=True, ensure_ascii=False)
    if key in cache:
        return cache[key]
    url = 'https://photon.komoot.io/api/?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    try:
        r = json.load(urllib.request.urlopen(req, timeout=25))
        feats = []
        for f in r.get('features', []):
            p = f['properties']
            lon, lat = f['geometry']['coordinates'][:2]
            feats.append({'lon': lon, 'lat': lat, 'name': p.get('name'),
                          'street': p.get('street'), 'housenumber': p.get('housenumber'),
                          'city': p.get('city')})
        cache[key] = feats
        json.dump(cache, open(CACHE_PATH, 'w'), ensure_ascii=False)
        time.sleep(1.1)
        return feats
    except Exception as e:
        print('   photon err:', e)
        return []

def hav(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * 6371 * math.asin(math.sqrt(h))

anchor_coords = {}
for anchor in d['stores_by_anchor']:
    if anchor in cache.get('__anchors__', {}):
        anchor_coords[anchor] = cache['__anchors__'][anchor]
        continue
    city, kw = anchor.split('-', 1)
    feats = photon(q=f'{kw} {city}', limit=1)
    if feats:
        anchor_coords[anchor] = [feats[0]['lon'], feats[0]['lat']]
        print(f'anchor {anchor} -> {anchor_coords[anchor]}')
    else:
        print(f'anchor {anchor} -> ✗')

ok = approx = fail = 0
for anchor, stores in d['stores_by_anchor'].items():
    city, kw = anchor.split('-', 1)
    A = anchor_coords.get(anchor)
    if not A:
        for st in stores:
            st['coord'] = None
        continue
    # 该地标周边的麦当劳 POI 候选池
    pois = photon(q='麦当劳', lat=A[1], lon=A[0], limit=15)
    for st in stores:
        mcp_d = (st.get('distance') or 1000) / 1000.0  # km
        addr = st.get('address') or ''
        m = re.match(r'(.+?[路街道巷])', addr)
        street = m.group(1) if m else ''
        # 按街道补一次搜索，扩大候选池
        cands = list(pois)
        if street:
            cands += photon(q=f'麦当劳 {street}', lat=A[1], lon=A[0], limit=8)
        seen, uniq = set(), []
        for poi in cands:
            k = (round(poi['lon'], 5), round(poi['lat'], 5))
            if k not in seen:
                seen.add(k)
                uniq.append(poi)
        best, best_score = None, 1e9
        for poi in uniq:
            c = (poi['lon'], poi['lat'])
            score = abs(hav(c, A) - mcp_d)
            if street and (street in (poi.get('street') or '') or (poi.get('street') or '') in addr):
                score -= 0.6  # 路名一致
            if poi.get('housenumber') and str(poi['housenumber']) in addr:
                score -= 0.8  # 门牌号一致
            if score < best_score:
                best, best_score = c, score
        if best and best_score < 1.0:
            st['coord'] = list(best)
            st['coord_quality'] = round(best_score, 3)
            ok += 1
        elif best and best_score < 2.0:
            st['coord'] = list(best)
            st['coord_quality'] = round(best_score, 3)
            approx += 1
        else:
            st['coord'] = list(A)  # 兜底：地标坐标
            st['coord_quality'] = -1
            fail += 1
        print(f"{'✓' if best_score < 1.0 else '≈' if best_score < 2.0 else '✗'} {st['storeName'][:18]:<20} score={best_score:.2f}km mcp_d={mcp_d:.2f}km")

json.dump(d, open(DATA, 'w'), ensure_ascii=False, indent=1)
d['anchor_coords'] = anchor_coords
json.dump(d, open(DATA, 'w'), ensure_ascii=False, indent=1)
print(f'\nDONE ok={ok} approx={approx} fallback={fail} total={ok+approx+fail}')
