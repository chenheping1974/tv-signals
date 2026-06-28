# tv-signals · 大宗商品 & A股 AI情报系统

> 每日自动采集 + DeepSeek AI 分析 + Kronos-small 选股排名  
> 零服务器 · 零月费 · 全自动

---

## 五个子系统

| | 📰 情报 | 🏆 Kronos选股 | 🛢 商品K线 | 🧠 Moirai排名 | 🚀 TimesFM排名 |
|------|------|------|------|------|------|
| 触发 | 21:00 | 16:30 工作日 | 08:00 | 11:00 | 22:00 工作日 |
| 信源 | 华尔街见闻 | 新浪A股 | 新浪全球期货 | 商品K线 | A股OHLCV |
| AI | DeepSeek | Kronos-small | — | Moirai-2 | TimesFM 2.5 |
| 输出 | RSS | ranking.json | csv.gz | moirai_ranking.json | timesfm_ranking.json |

---

## 整体架构

```
情报:   华尔街见闻 → Actions → DeepSeek → RSS → Feedly + Space
选股:   新浪A股 → Actions → Kronos → ranking.json → Space
商品K线: 新浪全球期货 → Actions → csv.gz + Chronos排名 → Space + Supabase
Moirai: 商品K线 → Actions → Moirai-2 → moirai_ranking.json → Space
TimesFM: A股OHLCV → Actions → TimesFM 2.5 → timesfm_ranking.json → Space
```

## HF Space

| Space | 标签 | 模型 |
|-------|------|------|
| [commodity-forecast](https://1348122919qqcom-commodity-forecast.hf.space) | Chronos商品 + Kronos A股 | Chronos-2 + Kronos-small |
| [timesfm-moirai](https://1348122919qqcom-timesfm-moirai.hf.space) | Moirai商品 + TimesFM A股 | Moirai-2 + TimesFM 2.5 |

## 目录

```
tv-signals/
├── feeds/                         RSS 输出
├── scripts/
│   ├── fetch_feeds.py             情报采集+AI分析
│   ├── stock_ranking.py           Kronos选股
│   ├── screen_pool.py             股票池筛选
│   ├── update_ohlcv.py            本地A股OHLCV增量
│   ├── update_commodities.py      商品OHLCV(新浪)
│   ├── commodity_ranking.py       Chronos-2商品排名
│   ├── moirai_ranking.py          Moirai-2商品排名
│   └── timesfm_ranking.py         TimesFM A股排名
├── data/
│   ├── stock_pool.json            股票池 (999只)
│   ├── ohlcv.csv.gz               A股OHLCV
│   ├── commodities_ohlcv.csv.gz    商品OHLCV (6品种)
│   ├── ranking.json               Kronos排名
│   ├── commodity_ranking.json     Chronos排名
│   ├── moirai_ranking.json        Moirai排名
│   └── timesfm_ranking.json       TimesFM排名
├── .github/workflows/
│   ├── daily-signals.yml          情报 (21:00)
│   ├── stock-ranking.yml          Kronos选股 (16:30)
│   ├── commodities-ohlcv.yml      商品K线+Chronos (08:00)
│   ├── moirai-ranking.yml         Moirai排名 (11:00)
│   └── timesfm-ranking.yml        TimesFM排名 (22:00)
└── docs/
```

## 成本

**$0/月** — GitHub Actions + Pages（公开仓库无限）/ DeepSeek ~$0.05 / 新浪/华尔街见闻 $0

## 相关链接

- Chronos+Kronos: https://1348122919qqcom-commodity-forecast.hf.space
- TimesFM+Moirai: https://1348122919qqcom-timesfm-moirai.hf.space
- Feedly: feeds/commodities.xml + a-stocks.xml
- Supabase: apfdgetfqxgbplariowa.supabase.co
