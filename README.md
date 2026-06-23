# tv-signals · 大宗商品 & A股 AI情报系统

> 每日自动采集 + DeepSeek AI 分析 + Kronos-small 选股排名  
> 零服务器 · 零月费 · 全自动

---

## 三个子系统

| | 📰 情报系统 | 🏆 选股系统 | 🛢 商品数据 |
|------|------|------|------|
| 触发 | 每天 21:00 | 每天 16:30 | 每天 08:00 |
| 信源 | 华尔街见闻 API | 新浪财经 OHLCV | 新浪全球期货 API |
| AI | DeepSeek | Kronos-small (24.7M) | — |
| 输出 | Feedly RSS | ranking.json → HF Space 榜单 | commodities_ohlcv.csv.gz |
| 标的 | 商品 + A股 | 999 只 A股 | 黄金/白银/原油/铜/铝/豆粕 |

---

## 整体架构

```
华尔街见闻 API ──→ GitHub Actions ──→ DeepSeek ──→ RSS XML ──→ Feedly
新浪财经 API   ──→ GitHub Actions ──→ Kronos-sm ──→ ranking.json ──→ HF Space
新浪全球期货    ──→ GitHub Actions ──→ commodities_ohlcv.csv.gz ──→ HF Space
```

## 目录

```
tv-signals/
├── feeds/                      RSS 输出
├── scripts/
│   ├── fetch_feeds.py          情报采集+AI 分析
│   ├── stock_ranking.py       选股批量预测
│   ├── update_ohlcv.py         本地OHLCV增量（A股）
│   └── update_commodities.py   商品OHLCV全量（新浪全球期货）
├── data/
│   ├── stock_pool.json         股票池 (999 只)
│   ├── ohlcv.csv.gz            A股OHLCV
│   ├── commodities_ohlcv.csv.gz 商品OHLCV (6品种,日线)
│   └── ranking.json            每日排序结果
├── .github/workflows/
│   ├── daily-signals.yml       情报 (21:00 北京)
│   ├── stock-ranking.yml       选股 (16:30 北京)
│   └── commodities-ohlcv.yml   商品数据 (08:00 北京)
└── docs/
```

## 成本

| 组件 | 月费 |
|------|------|
| GitHub Actions | $0（公开仓库无限） |
| GitHub Pages | $0 |
| DeepSeek API | ~$0.05 |
| 华尔街见闻 API | $0 |
| 新浪财经 API | $0 |
| 新浪全球期货 API | $0 |

**$0/月**

## 相关链接

- 预测平台：https://1348122919qqcom-commodity-forecast.hf.space
- Feedly：订阅 feeds/commodities.xml + a-stocks.xml
