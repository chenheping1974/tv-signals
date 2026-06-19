# 信源清单（当前状态）

## ✅ 已接入

| 信源 | 方式 | 频道 | 每日量 |
|------|------|------|--------|
| 华尔街见闻 | API: `api-prod.wallstreetcn.com/apiv1/content/lives/pc` | commodity, global, a_stock, forex | ~200条 |

华尔街见闻 API 返回 JSON，无需认证，按频道分组。我们抽取 4 个频道：

- `commodity` — 商品期货快讯（黄金、原油、铜、铝等）
- `global` — 全球宏观（美联储、央行、地缘政治）
- `a_stock` — A股市场快讯
- `forex` — 外汇市场（间接关联商品）

## ❌ 已测试不可用

| 信源 | 原因 |
|------|------|
| RSSHub 公共实例 | GitHub Actions IP 被 403 封禁 |
| 金十数据 API | `flash-api.jin10.com` 返回 502 |
| 金十数据 JS | `cdn.jin10.com/data_center/reports/flash_newest.js` 返回 404 |

## 🔮 后续可补充

| 信源 | 方式 | 价值 |
|------|------|------|
| 金十数据 | 找到可用 API 端点 | 商品快讯补充 |
| EIA 原油周报 | eia.gov 原生 RSS | 官方库存数据 |
| CFTC COT 持仓 | 网页抓取或 RSS | 投机持仓变化 |
| 上期所仓单 | 网页抓取 | 铜铝锌库存 |
| 东方财富 | 找到可用 API | A股公告+研报 |
| 财联社 | 找到可用 API | 政策解读 |
