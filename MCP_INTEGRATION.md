# MCP 集成说明（MCP_INTEGRATION.md）

> 麦麦热量回收计划 · 麦当劳程序员创意开发大赛参赛作品

## 1. 使用的麦当劳 MCP Server

| 项目 | 内容 |
|---|---|
| Server | 麦当劳中国 MCP Server（远程托管） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权 | `Authorization: Bearer ${MCD_MCP_TOKEN}`（仅构建期使用，真实 Token 不入库） |
| 配置示例 | 见 `mcp-config.example.json` |

## 2. 实际使用的 Tool

| Tool | 用途 | 调用时机 |
|---|---|---|
| `query-nearby-stores` | 查询用户位置附近可到店自取的麦当劳餐厅（门店名、地址、到店距离、营业时间） | 构建期抓取门店数据 |
| `list-nutrition-foods` | 获取 160 项麦当劳餐品的官方营养成分（能量 kJ/kcal、蛋白质、脂肪、碳水、钠、钙） | 构建期抓取营养库 |
| `query-meals` | 查询门店在售餐品列表（含餐品图片 URL），用于"热量回收"成果的图片化展示 | 构建期抓取餐品图库 |

全部为**只读查询类**工具。项目不调用 `create-order`、`cancel-order`、`mall-create-order`、`auto-bind-coupons` 等任何会修改账户或产生交易的工具。

### 调用参数要点（实测）

```jsonc
// query-nearby-stores
{ "beType": 1,            // 1=到店自取（本项目场景）
  "searchType": 2,        // 2=按位置搜索
  "city": "北京",          // 城市名
  "keyword": "西单" }      // 位置关键词

// list-nutrition-foods
{ }                       // 无参数，返回全量营养库

// query-meals
{ "storeCode": "1950008", // 门店编码，来自 query-nearby-stores
  "orderType": 1,         // 到店
  "beType": 1 }
```

## 3. 调用流程

```
构建期（tools/）                        运行期（浏览器，零 Token）
┌─────────────────────┐               ┌──────────────────────────┐
│ mcd_pipeline.py     │               │ index.html               │
│  ├ list-nutrition-  │               │  ├ 浏览器 Geolocation     │
│  │  foods → 营养库   │               │  ├ 最近门店匹配（构建数据）│
│  ├ query-nearby-    │  data.js      │  ├ OSRM 步行/骑行路线     │
│  │  stores → 门店    │ ────────────▶ │  ├ MET 公式算卡路里       │
│  └ query-meals      │  (打包内联)    │  └ 餐品当量换算 + 图片展示│
│     → 餐品图库      │               └──────────────────────────┘
│ geocode_stores.py   │
│  └ 门店坐标补全      │
└─────────────────────┘
```

**为什么按"构建期抓取"设计？** MCP Token 是敏感凭证，若由网页前端直接调用 MCP，Token 必然暴露在页面源代码/网络请求中，违反《参赛声明》的信息安全要求。因此本项目在构建期用 Token 抓取官方数据并打包为静态数据（`data.js`），网页运行期**无需任何凭证**，普通用户零配置即可使用。

## 4. 数据真实性

- **营养数据**：160 项餐品的能量/蛋白质/脂肪/碳水等全部字段来自 `list-nutrition-foods` 官方返回，页面换算基于此数据，未做人工修改。
- **餐品图片**：110 项餐品的图片 URL 来自 `query-meals` 返回的官方图片域 `menu-img.mcd.cn`；未匹配到官方图的餐品使用占位图卡。
- **门店数据**：门店名称、地址、营业时间、到店距离来自 `query-nearby-stores` 官方返回。采集采用 190+ 个北京地名关键词全城扫描（去重 450 家）；门店坐标为构建期估算：利用多家门店到各地标关键词的距离字段做多边定位（三角定位解算 250 家），辅以开源地图（Photon/OSM）地址编码，页面已标注"距离仅供参考"。
- **路线与热量**：步行/骑行路线由 OSRM（OpenStreetMap）真实路网计算；卡路里按 MET 公式估算（步行 3.8 MET、休闲骑行 5.0 MET，总消耗口径），页面已标注"热量为估算值"。

## 5. 业务价值

- **给"吃"一个运动的理由**：把官方营养数据从"劝退表"变成"回本账单"，用步行/骑行去门店的真实路程，直观展示"这趟路烧掉的卡路里 = 回收的餐品"。
- **鼓励到店自取的健康出行方式**：对比步行/骑行/外卖三种姿势的热量收支，潜移默化推荐更健康的到店方式。
- **MCP 能力的创新组合**：`query-nearby-stores`（找店）× `list-nutrition-foods`（营养）× `query-meals`（图片）三个查询工具的组合，加上开源路网能力，即开箱即用的"热量回收"体验，也提供 Agent Skill 形态（`skills/mcd-calorie-recycle/`）供 AI 助手直接调用。
