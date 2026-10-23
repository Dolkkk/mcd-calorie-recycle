#!/usr/bin/env python3
"""坐标解算：锚点反推 + 距离环多边定位，互相喂饭迭代。
输入 sweep_result.json / sweep_mcp_cache.json / data.json / photon_cache2.json
输出 solved_stores.json（450 家门店坐标 + 精度标签）"""
import json, math, os

HOME = os.path.expanduser('~')
D = f'{HOME}/mcd_data'
sweep = json.load(open(f'{D}/sweep_result.json'))
mcp_cache = json.load(open(f'{D}/sweep_mcp_cache.json'))
old = json.load(open(f'{D}/data.json'))
ph = json.load(open(f'{D}/photon_cache2.json'))

def hav(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 2 * 6371 * math.asin(math.sqrt(h))

def solve(pts):
    """pts: [([lon,lat], dist_km), ...] → (coord, resid_m)"""
    cx = sum(p[0][0] for p in pts) / len(pts)
    cy = sum(p[0][1] for p in pts) / len(pts)
    best, best_err = (cx, cy), 1e18
    for step, span in ((0.005, 0.025), (0.001, 0.005), (0.0002, 0.0012)):
        grid = []
        x0, y0 = best
        k = max(1, int(span / step))
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                x, y = x0 + dx * step, y0 + dy * step
                err = sum((hav((x, y), a) - d) ** 2 for a, d in pts)
                grid.append((err, (x, y)))
        grid.sort()
        best_err, best = grid[0]
    return best, math.sqrt(best_err / len(pts)) * 1000

# ---- 锚点库 ----
anchors = {}
for k, v in old.get('anchor_coords', {}).items():      # 老 8 锚点（北京-西单 → 西单）
    anchors[k.split('-', 1)[-1]] = list(v)
for key, feats in ph.items():                           # Photon 缓存里的锚点（仅限地名单点查询）
    try:
        meta = json.loads(key)
        q = meta.get('q', '')
        if meta.get('limit') == 1 and q.endswith(' 北京') and feats:
            kw = q[:-3]
            c = feats[0]['geometry']['coordinates'][:2]
            if kw not in anchors and 115.7 < c[0] < 117.4 and 39.4 < c[1] < 41.1:
                anchors[kw] = list(c)
    except Exception:
        pass
print(f'初始锚点：{len(anchors)} 个（老库 + Photon 缓存）')

# ---- 已知坐标门店（仅高质量：老 geo* 精修的）----
known = {}
for st in old['stores_by_anchor'].values():
    for s in st:
        note = s.get('coord_note', '')
        if note.startswith('geo') and s.get('coord'):
            known[s['storeCode']] = list(s['coord'])
print(f'已知坐标门店（种子）：{len(known)} 家')

stores = {s['storeCode']: s for s in sweep['stores']}

def rings_pts(rec, anchor_map):
    pts = []
    for kw, dist in rec['rings']:
        if kw in anchor_map and dist is not None:
            pts.append((anchor_map[kw], dist / 1000.0))
    return pts

# ---- 迭代：解门店 ↔ 反推锚点 ----
for it in range(20):
    new_stores = 0
    for code, rec in stores.items():
        if code in known:
            continue
        pts = rings_pts(rec, anchors)
        if len(pts) >= 2:
            coord, resid = solve(pts)
            if resid <= 700:
                known[code] = list(coord)
                rec['method'] = f'multilateration({len(pts)}环)' + ('' if resid <= 400 else '(noisy)')
                rec['resid_m'] = round(resid)
                new_stores += 1
    new_anchors = 0
    for kw, rows in mcp_cache.items():
        if kw in anchors or not rows:
            continue
        pts = []
        for s in rows:
            if s['storeCode'] in known and s.get('distance') is not None:
                pts.append((known[s['storeCode']], s['distance'] / 1000.0))
        if len(pts) >= 2:
            coord, resid = solve(pts)
            if resid <= 600:
                anchors[kw] = list(coord)
                new_anchors += 1
    print(f'迭代{it+1}: 新解门店 +{new_stores}（累计 {len(known)}）| 反推锚点 +{new_anchors}（累计 {len(anchors)}）')
    if new_stores == 0 and new_anchors == 0:
        break

# ---- 汇总输出 ----
out = {'generated_at': sweep['generated_at'], 'anchors': anchors, 'stores': []}
stats = {'multi': 0, 'old-precise': 0, 'unlocated': 0}
for code, rec in stores.items():
    coord, method, resid = None, 'unlocated', None
    if code in known:
        coord = known[code]
        if 'method' in rec:
            method, resid = rec['method'], rec.get('resid_m')
        else:
            method, resid = 'address-geocode(旧精修)', None
            stats['old-precise'] += 1
        if method.startswith('multilateration'):
            stats['multi'] += 1
    else:
        stats['unlocated'] += 1
    out['stores'].append({'storeCode': code, 'name': rec['name'], 'addr': rec['addr'],
                          'open': rec['open'], 'close': rec['close'], 'coord': coord,
                          'method': method, 'resid_m': resid, 'rings': rec['rings']})
json.dump(out, open(f'{D}/solved_stores.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f"\n解算完成：{stats}")
print(f"可上架（有坐标）：{len(known)} / {len(stores)} | 锚点总数：{len(anchors)}")
