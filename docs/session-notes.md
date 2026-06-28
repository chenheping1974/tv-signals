# 项目沟通笔记

## 系统总览

### 五个子系统

| 系统 | 功能 | 模型 | 触发 (北京时间) | 数据源 |
|------|------|------|------|--------|
| 📰 情报 | 商品+A股新闻 | DeepSeek | Actions 21:00 | 华尔街见闻 API |
| 🛢 商品K线+Chronos | 6品种K线+排名 | Chronos-2 | Actions 08:00 | 新浪全球期货 |
| 🧠 Moirai-2 | 商品排名+单支 | Moirai-2 Small | Actions 11:00 | 商品K线 |
| 🏆 Kronos选股 | A股排名 | Kronos-small | Actions 16:30 工作日 | 新浪A股 |
| 🚀 TimesFM 2.5 | A股排名+单支 | TimesFM 2.5 200M | Actions 22:00 工作日 | A股OHLCV |

成本: $0/月

---

## 数据链路

```
情报:   华尔街见闻 → Actions(21:00) → DeepSeek → RSS → Feedly + 两个Space
K线:    新浪全球期货 → Actions(08:00) → csv.gz → Chronos排名 → JSON + Supabase
Moirai: 商品K线 → Actions(11:00) → Moirai-2 → moirai_ranking.json
Kronos: 新浪A股 → Actions(16:30) → Kronos-sm → ranking.json
TimesFM: A股OHLCV → Actions(22:00) → TimesFM 2.5 → timesfm_ranking.json
```

---

## 两个 HF Space

| Space | 标签 | 模型 | 状态 |
|-------|------|------|------|
| `commodity-forecast` | Chronos商品 + Kronos A股 | Chronos-2 + Kronos-sm | ✅ 稳定 |
| `timesfm-moirai` | Moirai商品 + TimesFM A股 | Moirai-2 + TimesFM 2.5 | ✅ 运行中 |

### Space 地址
- Chronos+Kronos: https://1348122919qqcom-commodity-forecast.hf.space
- TimesFM+Moirai: https://1348122919qqcom-timesfm-moirai.hf.space

---

## Actions 时间线

| 时间 (北京) | 工作流 | 频率 |
|------------|--------|------|
| 08:00 | 商品K线 + Chronos排名 | 每天 |
| 11:00 | Moirai-2 排名 | 每天 |
| 16:30 | Kronos 选股 | 工作日 |
| 21:00 | 情报采集 | 每天 |
| 22:00 | TimesFM 排名 | 工作日 |

---

## 数据源

### 新浪全球期货 API
```
GET stock2.finance.sina.com.cn/futures/api/jsonp.php/
    ?symbol=GC&source=web
    /GlobalFuturesService.getGlobalFuturesDailyKLine
```

| 商品 | 新浪码 | 存储码 | 起始 |
|------|--------|--------|------|
| 黄金 | GC | GC=F | 2016-06 |
| 白银 | SI | SI=F | 2016-06 |
| 原油 | CL | CL=F | 1996-06 |
| 美铜 | HG | HG=F | 2016-06 |
| 伦铝 | AHD | AH=F | 2016-06 |
| 豆粕 | SM | ZM=F | 2016-06 |

- JSONP格式(需去壳), 无限流
- OHLC正常, 成交量除伦铝外为0

### 新浪A股 API
```
GET money.finance.sina.com.cn/quotes_service/api/json_v2.php/
    CN_MarketData.getKLineData?symbol=sh601899&datalen=400
```
- 纯JSON, datalen=N可控
- A股OHLCV约505根/股 (2024-04 ~ 2026-06)

---

## TimesFM 2.5 (Google)

### 模型信息
- 200M参数, Apache 2.0许可
- 最大上下文16K, 预测最多1024步
- 批量推理效率极高: 999只仅4.4分钟

### Space 使用 transformers 原生接口 ✅
```python
from transformers import TimesFm2_5ModelForPrediction
model = TimesFm2_5ModelForPrediction.from_pretrained(
    "google/timesfm-2.5-200m-transformers", device_map="auto"
)
outputs = model(past_values=[input_tensor], return_dict=True)
```

### 踩坑记录
- ❌ timesfm PyPI包在Space Python 3.11上全NaN
- ✅ 改用transformers原生接口解决
- ✅ accelerate依赖必须装

---

## Moirai-2 (Salesforce)

### 模型信息
- Small/Base/Large三档, CC-BY-NC-4.0许可
- 多变量预测(any-variate attention)
- 上下文默认1680

### 官方API ✅
```python
from uni2ts.model.moirai2 import Moirai2Forecast, Moirai2Module
model = Moirai2Forecast(module=Moirai2Module.from_pretrained(...), ...)
predictor = model.create_predictor(batch_size=1)
forecasts = predictor.predict(gluonts_dataset)
```

### 踩坑记录
- ❌ `from uni2ts.model.moirai` → v1旧版
- ✅ `from uni2ts.model.moirai2` → v2新版
- ❌ `model.forward()` → 内部方法, 参数不稳定
- ✅ `model.create_predictor()` → 官方公开API

---

## Supabase

- URL: `https://apfdgetfqxgbplariowa.supabase.co`
- 表: `commodity_rankings` (Chronos排名)
- 字段: updated, horizon, symbol, name, current, target, pct, low, high

---

## 文件结构

```
tv-signals/
├── feeds/
├── scripts/
│   ├── fetch_feeds.py            情报采集
│   ├── stock_ranking.py          Kronos选股
│   ├── screen_pool.py            股票池
│   ├── update_ohlcv.py           本地A股OHLCV
│   ├── update_commodities.py     商品OHLCV(新浪)
│   ├── commodity_ranking.py      Chronos排名
│   ├── moirai_ranking.py         Moirai排名
│   └── timesfm_ranking.py        TimesFM排名
├── data/
│   ├── stock_pool.json           (999只)
│   ├── ohlcv.csv.gz              A股OHLCV
│   ├── commodities_ohlcv.csv.gz  商品OHLCV(6品种)
│   ├── ranking.json              Kronos排名
│   ├── commodity_ranking.json    Chronos排名
│   ├── moirai_ranking.json       Moirai排名
│   └── timesfm_ranking.json      TimesFM排名
├── .github/workflows/
│   ├── daily-signals.yml         情报(21:00)
│   ├── stock-ranking.yml         Kronos(16:30)
│   ├── commodities-ohlcv.yml     商品K线+Chronos(08:00)
│   ├── moirai-ranking.yml        Moirai(11:00)
│   └── timesfm-ranking.yml       TimesFM(22:00)
└── docs/

chronos-app/                      → HF Space: commodity-forecast
timesfm-moirai/                   → HF Space: timesfm-moirai
```

---

## 核心教训

1. 新模型必须查官方文档验证API, 不能凭记忆写
2. Moirai-2: 模块名是`moirai2`不是`moirai`, 用`create_predictor()`不是`forward()`
3. TimesFM: transformers原生接口比PyPI包更稳
4. Python 3.10→3.11影响模型兼容性
5. 两个Space隔离部署, 互不影响
6. yfinance全链路不可靠, 已全面替换为新浪
7. 沟通文档保持最新
