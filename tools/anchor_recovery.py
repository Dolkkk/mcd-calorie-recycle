#!/usr/bin/env python3
"""锚点补考：给未锚定关键词重新从 Photon 拿坐标（清除负缓存后重试，限速保护）。"""
import json, os, time, urllib.parse, urllib.request

D = os.path.expanduser('~/mcd_data')
PH = f'{D}/photon_cache2.json'
solved = json.load(open(f'{D}/solved_stores.json'))
sweep = json.load(open(f'{D}/sweep_result.json'))
ph = json.load(open(PH))
anchors = solved['anchors']

missing = [kw for kw in sweep['keywords'] if kw not in anchors]
print(f'未锚定关键词 {len(missing)} 个：{missing[:20]}…')

ok = fail = 0
for i, kw in enumerate(missing):
    done = False
    for qform in (f'{kw} 北京', kw):
        key = json.dumps({'q': qform, 'limit': 1}, ensure_ascii=False)
        feats = ph.get(key)
        if feats:                      # 缓存已有有效结果
            c = feats[0]['geometry']['coordinates'][:2]
            if 115.7 < c[0] < 117.4 and 39.4 < c[1] < 41.1:
                anchors[kw] = list(c); ok += 1; done = True; break
        try:
            url = 'https://photon.komoot.io/api/?' + urllib.parse.urlencode({'q': qform, 'limit': 1})
            req = urllib.request.Request(url, headers={'User-Agent': 'mcd-anchor/1.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                feats = json.loads(r.read())['features']
            ph[key] = feats
            json.dump(ph, open(PH, 'w', encoding='utf-8'), ensure_ascii=False)
            if feats:
                c = feats[0]['geometry']['coordinates'][:2]
                if 115.7 < c[0] < 117.4 and 39.4 < c[1] < 41.1:
                    anchors[kw] = list(c); ok += 1; done = True
                    print(f'  ✅ {kw} -> {tuple(round(x,5) for x in c)}', flush=True)
                    break
        except Exception as e:
            print(f'  ❌ [{kw}] {e}', flush=True)
        time.sleep(0.8)
    if not done:
        fail += 1
    if (i + 1) % 15 == 0:
        print(f'  …进度 {i+1}/{len(missing)} | 拿到 {ok} | 失败 {fail}', flush=True)

solved['anchors'] = anchors
json.dump(solved, open(f'{D}/solved_stores.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'\n补考完成：新增锚点 {ok} | 仍缺 {fail} | 锚点总数 {len(anchors)}')
