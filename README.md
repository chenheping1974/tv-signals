# tv-signals · 大宗商品 & A股 AI情报系统

> 五个子系统 + 四个预测模型 + 零月费全自动

## 五个工作流

| # | 工作流 | 触发 | 模型 | 输出 |
|---|--------|------|------|------|
| 1 | commodities-ohlcv | 08:00 每天 | Chronos-2 | 商品K线 + 排名 |
| 2 | moirai-ranking | 11:00 每天 | Moirai-2 | 商品排名 7d-90d |
| 3 | stock-ranking | 16:30 工作日 | Kronos-small | A股排名 Top50 |
| 4 | daily-signals | 21:00 每天 | DeepSeek | RSS情报 |
| 5 | timesfm-ranking | 22:00 工作日 | TimesFM 2.5 | 全量+精选双排名 |

## 两个 HF Space

| Space | 模型 | 链接 |
|-------|------|------|
| commodity-forecast | Chronos-2 + Kronos-small | [hf.space](https://1348122919qqcom-commodity-forecast.hf.space) |
| timesfm-moirai | TimesFM 2.5 + Moirai-2 | [hf.space](https://1348122919qqcom-timesfm-moirai.hf.space) |

## 预测周期

| 模型 | 标的 | 周期 |
|------|------|------|
| Chronos-2 | 6品种商品 | 7d / 14d / 30d |
| Moirai-2 | 6品种商品 | 7d / 14d / 30d / 60d / 90d |
| Kronos-small | 999只A股 | 30d |
| TimesFM 2.5 | 5528只A股 | 30d / 60d / 128d |

## 数据源

- 商品K线: 新浪全球期货 API
- A股K线: 新浪 A股 API
- 情报: 华尔街见闻 API

全部免费, 无限流。

## 成本

$0/月。GitHub Actions (公开仓库无限) + GitHub Pages + HuggingFace Spaces (Free CPU) + DeepSeek ~$0.05。
