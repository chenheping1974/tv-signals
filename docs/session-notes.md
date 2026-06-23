# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 | 数据源 |
|------|------|------|------|--------|
| 📰 情报 | 商品+A股新闻 | DeepSeek | Actions 每天21:00 | 华尔街见闻 API |
| 🏆 选股 | A股横截面排序 | Kronos-small | Actions 每天16:30 | 新浪财经 A股API |
| 🛢 商品数据 | 6品种日线OHLCV | — | Actions 每天08:00 | 新浪全球期货 API |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | HF Space 按需 | 见下方数据链路 |

成本: $0/月

---

## 数据链路

```
情报:   华尔街见闻 ──→ Actions(21:00) ──→ DeepSeek ──→ RSS ──→ Feedly + Space
选股:   新浪A股API ──→ Actions(16:30) ──→ Kronos-sm ──→ ranking.json ──→ Space
商品:   新浪全球期货 ──→ Actions(08:00) ──→ commodities_ohlcv.csv.gz ──→ Space
```

### 各功能数据源明细

| 功能 | 数据来源 | 更新方式 | 缓存 |
|------|---------|---------|------|
| A股排行榜 Top50 | `ranking.json` (Actions跑) | Actions 16:30 全量跑 | GitHub |
| A股单支预测 (Kronos) | 新浪A股API `datalen=400` | 用户点击实时拉 | ❌ 无 |
| 商品排名 | `commodities_ohlcv.csv.gz` | Actions 08:00 全量 | `/home/user/` |
| 商品单支预测 (Chronos) | 同上 csv.gz | 同上 | `/home/user/` |

### 商品数据链路（2026-06-23 新建）

```
Actions(每天08:00北京 = UTC 00:00)
  → 新浪全球期货API (6品种全量日线, 3秒)
  → commodities_ohlcv.csv.gz → push 到 GitHub

HF Space 冷启动
  → ensure_commodity_csv() → GitHub raw 下载 → /home/user/

用户点预测/排名
  → 读 /home/user/commodities_ohlcv.csv.gz → 按symbol筛选 → Chronos-2
```

---

## 情报系统

- 华尔街见闻 API 4频道: commodity, global, a_stock, forex
- Actions UTC 13:00 → 北京时间 21:00
- DeepSeek 分析 → ≥2★商品 / ≥1★A股 → RSS XML
- GitHub Pages 托管 → Feedly订阅

---

## 选股系统

### 股票池
- 4条件过滤: ST/科创北交/市值>80亿/成交额>1亿 → 999只
- 每周一 `screen_pool.py` 重筛
- 本地 `update_ohlcv.py` 新浪增量 (datalen=10)

### OHLCV更新条件
- `data_date < today` → 新浪增量拉取
- `data_date >= today` → 跳过
- ⚠️ 曾有个 bug: 写的 `today - pd.Timedelta(days=1)`，差1天不触发，2026-06-23修复

### 排名跳过逻辑
- `ranking.updated >= data_date` → 排名已最新，跳过
- 防止延迟触发重复跑3小时Kronos

---

## 预测平台 (HF Space)

### 三个标签
| 标签 | 功能 | 模型 | 数据源 |
|------|------|------|--------|
| 🏭 商品预测 | 单支+排名+AI判断 | Chronos-2 | 新浪全球期货(csv.gz) |
| 🏦 A股预测 | 单支Kronos+Top50+目标价 | Kronos-small | 新浪A股API + ranking.json |
| 📡 情报 | 商品/A股RSS | — | GitHub Pages RSS |

### 持久化
- `/home/user/targets.json` — 目标价追踪 + 商品排名缓存，重启不丢
- `/home/user/commodities_ohlcv.csv.gz` — 商品OHLCV缓存，冷启动从GitHub下载

### 商品排名机制
- 当天首次点击 → 串行6个 Chronos-2 predict() → 排序 → 缓存到 targets.json
- 同日再点 → 读缓存
- 点"刷新排名" → force 重跑

### 目标价追踪
- 30天+90天目标价，Kronos预测反算
- 序号删除，标签切换自动刷新

---

## 数据源变迁

### yfinance 踩坑记录
- 批量下载 SQLite `database is locked`
- 逐只下载在 Actions 限流
- 2026-06-22 实测: 6商品 + A股全部 `YFRateLimitError`
- **结论: yfinance 不可靠，全局替换**

### 新浪全球期货 API
```
GET stock2.finance.sina.com.cn/futures/api/jsonp.php/
    ?symbol=GC&_=2026_6_22&source=web
    /GlobalFuturesService.getGlobalFuturesDailyKLine
```

| 商品 | 新浪码 | Yahoo码 | 数据起始 |
|------|--------|---------|----------|
| 黄金 | GC | GC=F | 2016-06 |
| 白银 | SI | SI=F | 2016-06 |
| 原油 | CL | CL=F | 1996-06 |
| 美铜 | HG | HG=F | 2016-06 |
| 伦铝 | AHD | AH=F | 2016-06 |
| 豆粕 | SM | ZM=F | 2016-06 |

- 10次连续请求全部200，无限流
- 返回JSONP（需去壳: 截取 `[` 到 `]`）
- 成交量除伦铝外为0（价格预测不受影响）
- 价格单位与Yahoo一致，2026-06-23已校准

### 新浪全球期货 vs 新浪A股 — 两个不同API

| | 全球期货 | A股 |
|------|---------|-----|
| 域名 | `stock2.finance.sina.com.cn` | `money.finance.sina.com.cn` |
| 路径 | `/futures/api/jsonp.php/` | `/quotes_service/api/json_v2.php/` |
| 返回格式 | JSONP | 纯JSON |
| 参数 | `symbol=GC` | `symbol=sh601899&scale=240&datalen=400` |
| 数据量控制 | 无，返回全量 | `datalen=N` |

---

## 文件结构

```
tv-signals/
├── feeds/                       RSS输出
│   ├── commodities.xml
│   └── a-stocks.xml
├── scripts/
│   ├── fetch_feeds.py           情报采集+AI分析
│   ├── stock_ranking.py         A股选股批量预测
│   ├── screen_pool.py           股票池筛选
│   ├── update_ohlcv.py          本地A股OHLCV增量
│   └── update_commodities.py    商品OHLCV全量
├── data/
│   ├── stock_pool.json          股票池 (999只)
│   ├── ohlcv.csv.gz             A股OHLCV
│   ├── commodities_ohlcv.csv.gz  商品OHLCV (6品种)
│   ├── ranking.json             每日排序
│   ├── signal_log.json          情报日志
│   └── processed_urls.json      去重索引
├── .github/workflows/
│   ├── daily-signals.yml        情报 (UTC 13:00)
│   ├── stock-ranking.yml        选股 (UTC 08:30, 工作日)
│   └── commodities-ohlcv.yml    商品数据 (UTC 00:00)
└── docs/

chronos-app/                     → HF Space
├── app.py                       主程序
├── requirements.txt
├── name_map.json                全量A股名→码映射
└── README.md
```

---

## 已知问题 & 注意事项

1. **GitHub Actions 调度延迟** — free tier 可延迟数小时，选股逻辑有跳过保护
2. **商品排名在 Space 跑** — 冷启动后首次要等模型加载+6个预测，比A股排名慢
3. **商品数据 Actions 首次触发** — 需验证 Actions 环境新浪API连通性
4. **Cron 显式写法** — `1-5` 可能不触发，用 `1,2,3,4,5`

---

## 核心教训

1. 先验证数据源 → 设计 → 代码
2. 用已验证过的数据源，不跳来跳去
3. yfinance 在 Actions 和本地均不可靠，已全局替换为新浪
4. Cron 用显式写法，避免范围格式
5. 增量只拉少量数据（datalen=10），不全量重下
6. 缓存放 `/home/user/`，防 HF Space 重启丢失
7. 数据源换之前必须校准价格
