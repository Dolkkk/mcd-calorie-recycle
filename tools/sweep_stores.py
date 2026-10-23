#!/usr/bin/env python3
"""全城撒网 v2：纯 MCP 收集（门店+到各关键词的距离环），不做地理编码。
解析用括号配平法；增量缓存断点续跑。坐标解算交给 solve_stages.py。"""
import json, os, time, urllib.request

HOME = os.path.expanduser('~')
TOKEN = open(f'{HOME}/mcd_token.txt').read().strip()
URL = 'https://mcp.mcd.cn'
D = f'{HOME}/mcd_data'
MCP_CACHE = f'{D}/sweep_mcp_cache.json'
OUT = f'{D}/sweep_result.json'

KEYWORDS = """王府井 东单 灯市口 金宝街 建国门 朝阳门 东直门 北新桥 安定门 交道口 雍和宫 磁器口 崇文门 广渠门 天坛 永定门 陶然亭 菜市口 广安门 长椿街 宣武门 复兴门 阜成门 西单 西直门 德胜门 积水潭 新街口 车公庄 金融街 什刹海 三里河 月坛 白纸坊 牛街 和平门 虎坊桥 珠市口 前门 大栅栏 朝阳公园 石佛营 十里堡 星火站 甜水园 呼家楼 金台夕照 团结湖 三里屯 工体 农业展览馆 亮马桥 燕莎 三元桥 太阳宫 芍药居 惠新西街 安贞 和平里 蒋宅口 亚运村 奥林匹克公园 北苑路 立水桥 天通苑 霍营 东小口 来广营 望京 花家地 酒仙桥 将台 东坝 常营 管庄 双桥 传媒大学 高碑店 四惠 大望路 国贸 建外SOHO 双井 劲松 潘家园 十里河 分钟寺 成寿寺 宋家庄 刘家窑 蒲黄榆 方庄 赵公口 木樨园 大红门 和义 东高地 万源路 亦庄 旧宫 瀛海 西红门 高米店 黄村 枣园 清源路 天宫院 生物医药基地 丰台科技园 丰台东大街 角门 洋桥 马家堡 草桥 纪家庙 花乡 新宫 南苑 青塔 大成路 六里桥 丽泽 北京西站 军事博物馆 公主坟 万寿路 五棵松 玉泉路 田村 永定路 世纪城 远大路 万柳 巴沟 蓟门桥 北太平庄 马甸 大钟寺 四季青 香山 西苑 圆明园 北宫门 清华东路 五道口 学院路 上地 西二旗 西三旗 清河 中关村 海淀黄庄 知春路 志新桥 健翔桥 安慧桥 沙河 昌平城区 未来科学城 通州北苑 果园 九棵树 梨园 临河里 土桥 环球影城 潞苑 苹果园 古城 八角 杨庄 鲁谷 衙门口 石景山万达 北京站 北京南站 北京北站 首都机场 大兴机场 朝阳站 清河站 丰台站 人民大学 清华大学 北京大学 北京航空航天大学 北京理工大学 对外经济贸易大学 中国传媒大学 北京工业大学 首都师范大学 北京交通大学 北京科技大学 北京邮电大学 中国农业大学 北京外国语大学 中央财经大学 中国人民公安大学""".split()
KEYWORDS = list(dict.fromkeys(KEYWORDS))

def post(body, session=None):
    data = json.dumps(body).encode()
    headers = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=60)
    sid = resp.headers.get("Mcp-Session-Id")
    raw = resp.read().decode("utf-8", "replace")
    payload = None
    if raw.lstrip().startswith("{"):
        payload = json.loads(raw)
    else:
        for line in raw.splitlines():
            if line.strip().startswith("data:"):
                try:
                    payload = json.loads(line.strip()[5:].strip())
                except Exception:
                    pass
    return payload, sid

def extract_json(txt):
    """括号配平扫描：返回第一个可解析的完整 JSON 对象"""
    start = txt.find('{')
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(txt)):
            ch = txt[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(txt[start:i + 1])
                        except Exception:
                            break
        start = txt.find('{', start + 1)
    return None

init, sid = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                             "clientInfo": {"name": "mcd-sweep2", "version": "1.0"}}})
try:
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
except Exception:
    pass
print("MCP ready:", init.get("result", {}).get("serverInfo", {}), flush=True)

mcp_cache = json.load(open(MCP_CACHE)) if os.path.exists(MCP_CACHE) else {}

def query_stores(kw):
    if kw in mcp_cache:
        return mcp_cache[kw]
    for attempt in range(3):
        try:
            r, _ = post({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                         "params": {"name": "query-nearby-stores",
                                    "arguments": {"beType": 1, "searchType": 2, "city": "北京", "keyword": kw}}}, sid)
            res = r.get("result", {}) or {}
            txt = "\n".join(c.get("text", "") for c in res.get("content", []))
            j = extract_json(txt)
            stores = []
            if j and j.get("success") and j.get("data"):
                stores = [{"storeCode": s.get("storeCode"), "storeName": s.get("storeName"),
                           "address": s.get("address"), "distance": s.get("distance"),
                           "open": s.get("businessStartTime"), "close": s.get("businessEndTime")}
                          for s in j["data"] if s.get("businessStatus")]
            if not stores:
                print(f"   空结果 [{kw}] txt_head={txt[:60]!r}", flush=True)
            mcp_cache[kw] = stores
            json.dump(mcp_cache, open(MCP_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
            return stores
        except Exception as e:
            print(f"   mcp retry {attempt+1} [{kw}]: {e}", flush=True)
            time.sleep(2)
    mcp_cache[kw] = []
    json.dump(mcp_cache, open(MCP_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return []

print(f"关键词 {len(KEYWORDS)} 个，纯 MCP 撒网…", flush=True)
rings = {}
total_hits = 0
for i, kw in enumerate(KEYWORDS):
    for s in query_stores(kw):
        total_hits += 1
        rec = rings.setdefault(s["storeCode"], {"name": s["storeName"], "addr": s["address"],
                                                "open": s["open"], "close": s["close"], "rings": []})
        if s.get("distance") is not None:
            rec["rings"].append([kw, float(s["distance"])])
    if (i + 1) % 30 == 0:
        print(f"  进度 {i+1}/{len(KEYWORDS)} | 去重后 {len(rings)} 家 | 命中 {total_hits} 条", flush=True)

result = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "keywords": KEYWORDS, "stores": []}
for code, rec in rings.items():
    result["stores"].append({"storeCode": code, "name": rec["name"], "addr": rec["addr"],
                             "open": rec["open"], "close": rec["close"], "rings": rec["rings"]})
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
multi = sum(1 for r in rings.values() if len(r["rings"]) >= 2)
print(f"\n撒网完成：命中 {total_hits} 条 | 去重 {len(rings)} 家 | 多环候选 {multi} 家")
print("输出:", OUT)
