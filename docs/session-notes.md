# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 (北京时间) | 数据源 |
|------|------|------|------|--------|
| 📰 情报 | 商品+A股新闻 | DeepSeek | Actions 21:00 | 华尔街见闻 API |
| 🏆 选股 | A股横截面排序 | Kronos-small | Actions 16:30 工作日 | 新浪 A股 API |
| 🛢 商品数据 | 6品种日线OHLCV | — | Actions 08:00 | 新浪全球期货 API |
| 🤖 商品排名 | 6品种7d/14d/30d预测 | Chronos-2 | Actions 08:00 (数据后) | 同上 K线 |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | HF Space 按需 | 下表 |

成本: $0/月

---

## 数据链路

```
情报:   华尔街见闻 → Actions(21:00) → DeepSeek → RSS XML → Feedly + Space
选股:   新浪A股API → Actions(16:30) → Kronos-sm → ranking.json → Space
商品K线: 新浪全球期货 → Actions(08:00) → commodities_ohlcv.csv.gz → GitHub + Space
商品排名: (等K线完成) → Chronos-2 → commodity_ranking.json → GitHub + Supabase
```

### 各功能数据源明细

| 功能 | 来源 | 更新方式 | 缓存/存储 |
|------|------|---------|----------|
| A股排行榜 | ranking.json | Actions 16:30 全量999只 | GitHub |
| A股单支预测 | 新浪A股API `datalen=400` | 点击实时拉 | 无 |
| 商品K线 | commodities_ohlcv.csv.gz | Actions 08:00 全量 | GitHub + `/home/user/` |
| 商品排名 | commodity_ranking.json | Actions 08:00 (K线后) | GitHub + Supabase |
| 商品单支预测 | 同上 K线 | 点击读本地 csv.gz | Chronos-2 现场跑 |

---

## 商品排名系统 (2026-06-26 新建)

### 工作流 — 合并在一个文件
`commodities-ohlcv.yml`:
```
Step 1 (update):  拉新浪全球期货 → csv.gz → git push
Step 2 (ranking): Chronos-2 → 6品种预测 → ranking.json → git push + Supabase
                   (update 完成才触发)
```

### 预测输出
```json
{
  "updated": "2026-06-26T14:58:29",
  "data_date": "2026-06-26",
  "rankings": {
    "7d":  [{"symbol":"GC=F","name":"现货黄金","current":4103.10,"target":4050.00,"pct":-1.3,"low":...,"high":...}, ...],
    "14d": [...],
    "30d": [...]
  },
  "details": [...]
}
```

### 外部调用
```
# GitHub raw
https://raw.githubusercontent.com/chenheping1974/tv-signals/main/data/commodity_ranking.json

# Supabase
supabase.from("commodity_rankings").select("*").eq("horizon","30d").order("pct")
```

### Supabase 配置
- URL: `https://apfdgetfqxgbplariowa.supabase.co`
- 表: `commodity_rankings`
- 字段: updated, horizon, symbol, name, current, target, pct, low, high

---

## Actions 工作流汇总

| 工作流 | cron (UTC) | 北京时间 | 说明 |
|--------|-----------|---------|------|
| `daily-signals.yml` | `0 13 * * *` | 21:00 | 情报采集 |
| `stock-ranking.yml` | `30 8 * * 1,2,3,4,5` | 16:30 | A股选股 |
| `commodities-ohlcv.yml` | `0 0 * * *` | 08:00 | 商品K线+排名 |

⚠️ GitHub Actions free tier 不保证准时，可延迟数小时。选股逻辑有跳过保护。

---

## 预测平台 (HF Space)

### 标签功能

| 标签 | 功能 | 模型 | 数据 |
|------|------|------|------|
| 🏭 商品预测 | 单支 + 排名表格 + AI判断 | Chronos-2 | 新浪 |
| 🏦 A股预测 | Kronos单支 + Top50 + 目标价 | Kronos-small | 新浪 |
| 📡 情报 | 商品/A股 RSS | — | GitHub Pages |

### 商品排名表格
- 从 GitHub 拉预计算的 `commodity_ranking.json`，秒出
- 三列并排: 7天 / 14天 / 30天 目标价
- 按30天涨幅排序，红涨绿跌
- 移动端适配

### 持久化
- `/home/user/targets.json` — 目标价
- `/home/user/commodities_ohlcv.csv.gz` — 商品K线 (冷启动从GitHub下载)

---

## 情报系统

- 华尔街见闻 4频道: commodity / global / a_stock / forex
- Actions UTC 13:00 → 北京时间 21:00
- DeepSeek 分析 → ≥2★进商品Feed / ≥1★进A股Feed
- 输出: GitHub Pages RSS → Feedly 订阅
- RSS URL:
  - `https://chenheping1974.github.io/tv-signals/feeds/commodities.xml`
  - `https://chenheping1974.github.io/tv-signals/feeds/a-stocks.xml`

---

## 选股系统

### 股票池
- 4条件过滤: 排除ST/科创北交 + 市值>80亿 + 成交额>1亿 → 999只
- 每周一 `screen_pool.py` 重筛

### OHLCV 更新
- `data_date < today` → 新浪增量 (datalen=10)
- ⚠️ 曾写 `today - pd.Timedelta(days=1)`，差1天不触发，已修复

### 排名跳过
- `ranking.updated >= data_date` → 跳过（防延迟重复跑3h）

---

## 数据源

### yfinance → 新浪 (全面替换)

| 阶段 | 原数据源 | 问题 | 现数据源 |
|------|---------|------|---------|
| A股选股 | yfinance | SQLite锁/IP限流 | 新浪A股API |
| A股单支 | yf→fallback | yf白等3s | 纯新浪A股API |
| 商品预测 | yfinance | 6品种全限流 | 新浪全球期货API |

### 新浪全球期货 API

```
GET stock2.finance.sina.com.cn/futures/api/jsonp.php/
    ?symbol=GC&source=web
    /GlobalFuturesService.getGlobalFuturesDailyKLine
```

| 商品 | 新浪码 | 存储码 | 数据起始 | 成交量 |
|------|--------|--------|----------|--------|
| 黄金 | GC | GC=F | 2016-06 | 无 |
| 白银 | SI | SI=F | 2016-06 | 无 |
| 原油 | CL | CL=F | 1996-06 | 无 |
| 美铜 | HG | HG=F | 2016-06 | 无 |
| 伦铝 | AHD | AH=F | 2016-06 | 有 |
| 豆粕 | SM | ZM=F | 2016-06 | 无 |

- 返回JSONP (需去壳)，6品种全量3秒，无限流
- 价格与市场一致，已校准

### 新浪全球期货 vs 新浪A股 — 不同API

| | 全球期货 | A股 |
|------|---------|-----|
| 域名 | `stock2.finance.sina.com.cn` | `money.finance.sina.com.cn` |
| 路径 | `/futures/api/jsonp.php/` | `/quotes_service/api/json_v2.php/` |
| 返回 | JSONP | JSON |
| 数据量 | 全量 | `datalen=N` 可控 |

---

## 文件结构

```
tv-signals/
├── feeds/                        RSS输出
├── scripts/
│   ├── fetch_feeds.py            情报采集+AI分析
│   ├── stock_ranking.py          A股选股(Kronos)
│   ├── screen_pool.py            股票池筛选
│   ├── update_ohlcv.py           本地A股OHLCV增量
│   ├── update_commodities.py     商品OHLCV(新浪)
│   └── commodity_ranking.py      商品排名(Chronos-2)
├── data/
│   ├── stock_pool.json           股票池 (999只)
│   ├── ohlcv.csv.gz              A股OHLCV
│   ├── commodities_ohlcv.csv.gz   商品OHLCV (6品种)
│   ├── ranking.json              A股排名
│   ├── commodity_ranking.json    商品排名 (7d/14d/30d)
│   ├── signal_log.json           情报日志
│   └── processed_urls.json       去重索引
├── .github/workflows/
│   ├── daily-signals.yml         情报 (21:00)
│   ├── stock-ranking.yml         选股 (16:30)
│   └── commodities-ohlcv.yml     商品K线+排名 (08:00)
└── docs/

chronos-app/                      → HF Space
├── app.py
├── requirements.txt
├── name_map.json                 全量A股名→码
└── README.md
```

---

## 已修复问题汇总

| 日期 | 问题 | 修复 |
|------|------|------|
| 06-23 | OHLCV更新 off-by-one | `stock_ranking.py:85` |
| 06-23 | 商品 yfinance 全限流 | 换新浪全球期货 |
| 06-23 | 商品无定时更新 | Actions 08:00 |
| 06-23 | Space 商品直调 yf | 读 csv.gz |
| 06-23 | A股单支 yf 白等3s | 纯新浪 |
| 06-23 | CSV 丢 date 列 | `app.py:431` |
| 06-23 | README 缺 YAML | 补元数据 |
| 06-23 | huggingface_hub 冲突 | gradio/hf_hub 解索 |
| 06-23 | sdk_version 冲突 | 移除 |
| 06-26 | pip --index-url 冲突 | 分开装 |
| 06-26 | 商品排名手动触发 | Actions 定时 + Supabase |
| 06-26 | 排名表格适配 | 三列价格+移动端 |

## 核心教训

1. 先验证数据源 → 再设计 → 再写代码
2. yfinance 全链路不可靠，已全面替换为新浪
3. CSV 列映射/timestamp 转换，换源必校验
4. requirements.txt 不锁版本上限，跟 HF Space 默认版本
5. pip install 时 `--index-url` 会覆盖默认源，torch 必须单独装
6. 缓存放 `/home/user/`，防 Space 重启丢
7. 数据源校准后再上线
8. 沟通文档保持最新，做完改动即时更新
