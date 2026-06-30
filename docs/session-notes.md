# 项目沟通笔记

## 系统总览

### 五个子系统 + 两个 Space

| 系统 | 功能 | 模型 | 工作流 | 触发 | 数据源 |
|------|------|------|--------|------|--------|
| 🛢 商品K线+Chronos | 6品种K线+排名 | Chronos-2 | commodities-ohlcv | 08:00 每天 | 新浪全球期货 |
| 🧠 Moirai-2 | 商品排名+单支 | Moirai-2 Small | moirai-ranking | 11:00 每天 | 商品K线 |
| 🏆 Kronos选股 | A股排名 | Kronos-small | stock-ranking | 16:30 工作日 | 新浪A股 |
| 📰 情报 | 商品+A股新闻 | DeepSeek | daily-signals | 21:00 每天 | 华尔街见闻 |
| 🚀 TimesFM | A股全量+精选排名 | TimesFM 2.5 | timesfm-ranking | 22:00 工作日 | 新浪A股 |

| Space | 标签 | 模型 |
|-------|------|------|
| [commodity-forecast](https://1348122919qqcom-commodity-forecast.hf.space) | 商品预测 / A股预测 / 情报 | Chronos-2 + Kronos-small |
| [timesfm-moirai](https://1348122919qqcom-timesfm-moirai.hf.space) | Moirai商品 / TimesFM A股 | Moirai-2 + TimesFM 2.5 |

成本: $0/月

---

## 五个工作流

### 1. commodities-ohlcv.yml — 商品K线 + Chronos排名
- **触发**: UTC 00:00 = 北京时间 08:00，每天
- **jobs**: update(拉K线) → ranking(Chronos-2预测)
- **输出**: `commodities_ohlcv.csv.gz` / `commodity_ranking.json` + Supabase

### 2. moirai-ranking.yml — Moirai-2商品排名
- **触发**: UTC 03:00 = 北京时间 11:00，每天
- **job**: 读K线 → Moirai-2 → `moirai_ranking.json`
- **周期**: 7d / 14d / 30d / 60d / 90d

### 3. stock-ranking.yml — Kronos A股选股
- **触发**: UTC 08:30 = 北京时间 16:30，工作日
- **job**: 新浪增量 → Kronos-small 999只 → `ranking.json`

### 4. daily-signals.yml — 情报采集
- **触发**: UTC 13:00 = 北京时间 21:00，每天
- **job**: 华尔街见闻4频道 → DeepSeek → RSS XML

### 5. timesfm-ranking.yml — TimesFM A股全量+精选
- **触发**: UTC 14:00 = 北京时间 22:00，工作日
- **jobs**: update_full(K线) → full_ranking(全量预测) → filter_999(筛精选)
- **输出**: `timesfm_full_ranking.json` / `timesfm_ranking.json`
- **周期**: 30d / 60d / 128d
- **K线**: 5528只全量, tail(600)控制100MB内, 连续200只无新数据自动跳过

---

## 数据链路

```
K线:     新浪全球期货 → Actions 08:00 → csv.gz → Chronos排名 → JSON + Supabase
Moirai:  商品K线 → Actions 11:00 → Moirai-2 → moirai_ranking.json
Kronos:  新浪A股 → Actions 16:30 → Kronos-sm → ranking.json
情报:    华尔街见闻 → Actions 21:00 → DeepSeek → RSS → Feedly + Space
TimesFM: 新浪A股全量 → Actions 22:00 → TimesFM 2.5 → 全量+精选双JSON
```

---

## 预测周期

| 模型 | 周期 | 步数 |
|------|------|------|
| Chronos-2 | 7d / 14d / 30d | 5 / 10 / 22 |
| Moirai-2 | 7d / 14d / 30d / 60d / 90d | 5 / 10 / 22 / 44 / 66 |
| Kronos-small | 30d | 22 |
| TimesFM 2.5 | 30d / 60d / 128d | 22 / 44 / 128 |

---

## 数据源

### 新浪全球期货 API
```
GET stock2.finance.sina.com.cn/futures/api/jsonp.php/
    ?symbol=GC&source=web
    /GlobalFuturesService.getGlobalFuturesDailyKLine
```
6品种, JSONP格式, 无限流

### 新浪A股 API
```
GET money.finance.sina.com.cn/quotes_service/api/json_v2.php/
    CN_MarketData.getKLineData?symbol=sh601899&datalen=400
```
纯JSON, datalen可控

---

## 模型经验

### TimesFM 2.5
- Space: transformers版本 (兼容性好)
- Actions: timesfm PyPI包 (compile()后快5倍)
- 批量: 200只/批, 38-50秒/批

### Moirai-2
- 官方API: `from uni2ts.model.moirai2` + `create_predictor()` + GluonTS
- ❌ 不可 `forward()`

---

## 文件结构

```
tv-signals/
├── feeds/                          RSS输出
├── scripts/
│   ├── fetch_feeds.py              DeepSeek情报
│   ├── stock_ranking.py            Kronos选股
│   ├── screen_pool.py              股票池
│   ├── update_ohlcv.py             本地A股增量
│   ├── update_commodities.py       商品K线(新浪全球期货)
│   ├── update_ohlcv_full.py        全量A股K线(5528只)
│   ├── commodity_ranking.py        Chronos排名
│   ├── moirai_ranking.py           Moirai排名
│   ├── timesfm_ranking.py          (保留未用)
│   └── timesfm_full_ranking.py     TimesFM全量排名
├── data/
│   ├── stock_pool.json             (999只)
│   ├── name_map.json               (5528股名码)
│   ├── ohlcv.csv.gz                A股Kronos用
│   ├── ohlcv_full.csv.gz           全量A股
│   ├── commodities_ohlcv.csv.gz    商品K线
│   ├── ranking.json                Kronos排名
│   ├── commodity_ranking.json      Chronos排名
│   ├── moirai_ranking.json         Moirai排名
│   ├── timesfm_ranking.json        精选排名
│   └── timesfm_full_ranking.json   全量排名
├── .github/workflows/
│   ├── commodities-ohlcv.yml       08:00 每天
│   ├── moirai-ranking.yml          11:00 每天
│   ├── stock-ranking.yml           16:30 工作日
│   ├── daily-signals.yml           21:00 每天
│   └── timesfm-ranking.yml         22:00 工作日
└── docs/

chronos-app/                        → HF Space: commodity-forecast
timesfm-moirai/                     → HF Space: timesfm-moirai
```

---

## UI 优化

- 所有标签/标题/按钮去 emoji
- TimesFM单支预测去天数选择，点按钮直接输出30d/60d/128d
- 目标价追踪表删序号列，适配手机
- 商品排名品种名全显示
- 启动优化: 所有`gr.HTML(value=...)`初始值改占位，切标签/点刷新才拉数据

## 核心教训

1. 推送前必须征得用户同意
2. timesfm包在Actions快、transformers在Space稳，各用各的
3. 新模型必须查官方文档验证API
4. git add 先于 git pull
5. Actions runner数据不持久
6. 两个Space隔离，互不影响
7. yfinance全链路不可靠，已全面替换新浪
8. 全量K线 tail(600) 控制100MB
9. 连续200只无新数据=休市跳过
10. 沟通文档保持最新
