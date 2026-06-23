# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 (北京时间) | 数据源 |
|------|------|------|------|--------|
| 📰 情报 | 商品+A股新闻 | DeepSeek | Actions 21:00 | 华尔街见闻 API |
| 🏆 选股 | A股横截面排序 | Kronos-small | Actions 16:30 工作日 | 新浪 A股 API |
| 🛢 商品数据 | 6品种日线OHLCV | — | Actions 08:00 | 新浪全球期货 API |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | HF Space 按需 | 下表 |

成本: $0/月

---

## 数据链路

```
情报:  华尔街见闻 API → Actions → DeepSeek → RSS XML → Feedly + Space情报页
选股:  新浪A股API → Actions → Kronos-sm → ranking.json → Space A股页
商品:  新浪全球期货 → Actions → commodities_ohlcv.csv.gz → Space 商品页
```

### 各功能数据源明细

| 功能 | 来源 | 更新方式 | 缓存位置 |
|------|------|---------|---------|
| A股排行榜 Top50 | ranking.json (Actions跑) | 16:30 全量999只 | GitHub |
| A股单支预测 (Kronos) | 新浪A股API `datalen=400` | 点击实时拉 | 无 |
| 商品单支预测 (Chronos-2) | commodities_ohlcv.csv.gz | Actions 08:00 | `/home/user/` |
| 商品排名 | 同上 csv.gz | 同上 | `/home/user/targets.json` |

---

## 情报系统

- 华尔街见闻 4频道: commodity / global / a_stock / forex
- GitHub Actions UTC 13:00 → 北京时间 21:00
- DeepSeek 分析 → ≥2★进商品Feed / ≥1★进A股Feed
- 输出: GitHub Pages RSS → Feedly 订阅

---

## 选股系统

### 股票池
- 4条件过滤: 排除ST/科创北交 + 市值>80亿 + 成交额>1亿 → 999只
- 每周一 `screen_pool.py` 重筛
- 本地 `update_ohlcv.py` 增量: 新浪 `datalen=10`

### OHLCV 更新条件
```python
if data_date < today:   # 昨天的数据 → 拉增量
```
⚠️ 曾写 `today - pd.Timedelta(days=1)`，差1天不触发，2026-06-23 修复。

### 排名跳过逻辑
```python
if ranking.updated >= data_date:  # 排名已覆盖最新数据 → 跳过
```
防止延迟触发重复跑 3 小时 Kronos。

---

## 预测平台 (HF Space)

### 标签

| 标签 | 功能 | 模型 | 数据 |
|------|------|------|------|
| 🏭 商品预测 | 单支 + 排名 + AI判断 | Chronos-2 (120M) | 新浪全球期货 |
| 🏦 A股预测 | Kronos单支 + Top50 + 目标价 | Kronos-small (24.7M) | 新浪A股 |
| 📡 情报 | 商品/A股 RSS | — | GitHub Pages |

### 持久化
- `/home/user/targets.json` — 目标价 + 商品排名缓存
- `/home/user/commodities_ohlcv.csv.gz` — 商品OHLCV，冷启动从 GitHub 下载

### 商品排名机制
- 当天首次 → 串行 6 个 predict() → 排序 → 缓存
- 同天再点 → 读缓存
- "刷新排名" → force 重跑

### 目标价追踪
- Kronos 预测 30天+90天目标价
- 持久化到 `targets.json`，重启不丢

---

## 数据源

### yfinance → 新浪 (2026-06-23)

| 阶段 | 数据源 | 问题 |
|------|--------|------|
| 初期 | yfinance | SQLite锁 / IP限流 |
| A股选股 | → 新浪A股API | ✅ 稳定 |
| A股单支预测 | yf → fallback 新浪 | yf白等3s |
| 商品预测 | yfinance | 6品种全部限流 |
| 商品预测 | → 新浪全球期货API | ✅ 稳定 |

### 新浪全球期货 API

```
GET stock2.finance.sina.com.cn/futures/api/jsonp.php/
    ?symbol=GC&_=2026_6_23&source=web
    /GlobalFuturesService.getGlobalFuturesDailyKLine
```

| 商品 | 新浪码 | CSV码 | 数据起始 | 成交量 |
|------|--------|-------|----------|--------|
| 黄金 | GC | GC=F | 2016-06 | 无 |
| 白银 | SI | SI=F | 2016-06 | 无 |
| 原油 | CL | CL=F | 1996-06 | 无 |
| 美铜 | HG | HG=F | 2016-06 | 无 |
| 伦铝 | AHD | AH=F | 2016-06 | 有 |
| 豆粕 | SM | ZM=F | 2016-06 | 无 |

- 返回 JSONP (截 `[` 到 `]` 去壳)
- 无 datalen 参数，每次全量 (~2500行/品种)
- 6 品种全量 3 秒，无限流
- OHLC 价格与市场一致，2026-06-23 已校准

### 新浪全球期货 vs 新浪A股 — 两个不同API

| | 全球期货 | A股 |
|------|---------|-----|
| 域名 | `stock2.finance.sina.com.cn` | `money.finance.sina.com.cn` |
| 路径 | `/futures/api/jsonp.php/` | `/quotes_service/api/json_v2.php/` |
| 返回 | JSONP | JSON |
| 参数 | `symbol=GC` | `symbol=sh601899&datalen=400` |

---

## Actions 工作流

| 工作流 | cron (UTC) | 北京时间 | 说明 |
|--------|-----------|---------|------|
| `daily-signals.yml` | `0 13 * * *` | 21:00 | 情报采集 |
| `stock-ranking.yml` | `30 8 * * 1,2,3,4,5` | 16:30 | A股选股 |
| `commodities-ohlcv.yml` | `0 0 * * *` | 08:00 | 商品数据 |

⚠️ GitHub Actions free tier 不保证准时，可延迟数小时。选股逻辑有跳过保护。

---

## 文件结构

```
tv-signals/
├── feeds/                        RSS输出
│   ├── commodities.xml
│   └── a-stocks.xml
├── scripts/
│   ├── fetch_feeds.py            情报采集+AI分析
│   ├── stock_ranking.py          A股选股批量预测
│   ├── screen_pool.py            股票池筛选
│   ├── update_ohlcv.py           本地A股OHLCV增量
│   └── update_commodities.py     商品OHLCV全量(新浪全球期货)
├── data/
│   ├── stock_pool.json           股票池 (999只)
│   ├── ohlcv.csv.gz              A股OHLCV
│   ├── commodities_ohlcv.csv.gz   商品OHLCV (6品种 日线)
│   ├── ranking.json              每日排序
│   ├── signal_log.json           情报日志
│   └── processed_urls.json       去重索引
├── .github/workflows/
│   ├── daily-signals.yml         情报
│   ├── stock-ranking.yml         选股
│   └── commodities-ohlcv.yml     商品数据
└── docs/

chronos-app/                      → HF Space
├── app.py
├── requirements.txt              gradio<5, huggingface_hub<1.0
├── name_map.json                 全量A股名→码 (5528条)
└── README.md
```

---

## 已修复问题

| 日期 | 问题 | 修复 |
|------|------|------|
| 06-23 | OHLCV更新条件 off-by-one | `stock_ranking.py:85` |
| 06-23 | 商品 yfinance 全限流 | 换新浪全球期货 |
| 06-23 | 商品无定时更新 | Actions 08:00 |
| 06-23 | Space 商品直调 yf | 读 csv.gz |
| 06-23 | A股单支 yf 白等 3s | 纯新浪 |
| 06-23 | CSV 读丢 date 列 | `app.py:431` |
| 06-23 | README 缺 YAML | 补元数据 |
| 06-23 | huggingface_hub 冲突 | 锁 gradio<5, hf_hub<1.0 |

## 核心教训

1. 先验证数据源 → 再设计 → 再写代码
2. yfinance 全链路不可靠，已全面替换为新浪
3. CSV 列映射、timestamp 转换，换数据源必校验
4. requirements.txt 锁版本范围，防大版本升级炸
5. 缓存放 `/home/user/`，防 Space 重启丢
6. 数据源换之前必须校准价格
7. 沟通文档保持最新，每次做完改动即时更新
