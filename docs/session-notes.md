# 项目沟通笔记

## 系统总览

### 五个工作流 + 四个模型 + 两个 Space

| 工作流 | 触发 | 模型 | 输出 | 数据源 |
|--------|------|------|------|--------|
| commodities-ohlcv | 08:00 每天 | Chronos-2 | K线 + 商品排名 | 新浪全球期货 |
| moirai-ranking | 11:00 每天 | Moirai-2 | 商品排名 | 商品K线 |
| stock-ranking | 16:30 工作日 | Kronos-small | A股排名 | 新浪A股 |
| daily-signals | 21:00 每天 | DeepSeek | RSS情报 | 华尔街见闻 |
| timesfm-ranking | 22:00 工作日 | TimesFM 2.5 | 全量+精选排名 | 新浪A股 |

### 排名输出 (5份)

| 文件 | 模型 | 标的 | 周期 | URL |
|------|------|------|------|-----|
| `commodity_ranking.json` | Chronos-2 | 6品种商品 | 7d/14d/30d | [raw](https://raw.githubusercontent.com/chenheping1974/tv-signals/main/data/commodity_ranking.json) |
| `moirai_ranking.json` | Moirai-2 | 6品种商品 | 7d/14d/30d/60d/90d | [raw](https://raw.githubusercontent.com/chenheping1974/tv-signals/main/data/moirai_ranking.json) |
| `ranking.json` | Kronos-sm | 999精选A股 | 30d | [raw](https://raw.githubusercontent.com/chenheping1974/tv-signals/main/data/ranking.json) |
| `timesfm_ranking.json` | TimesFM 2.5 | 999精选A股 | 30d/60d/128d | [raw](https://raw.githubusercontent.com/chenheping1974/tv-signals/main/data/timesfm_ranking.json) |
| `timesfm_full_ranking.json` | TimesFM 2.5 | 5528全量A股 | 30d/60d/128d | [raw](https://raw.githubusercontent.com/chenheping1974/tv-signals/main/data/timesfm_full_ranking.json) |

### 两个 Space (纯预测, 无排名/情报)

| Space | 标签1 | 标签2 | 链接 |
|-------|------|------|------|
| commodity-forecast | Chronos-2 商品单支 | Kronos-small A股单支 | [hf.space](https://1348122919qqcom-commodity-forecast.hf.space) |
| timesfm-moirai | Moirai-2 商品单支 | TimesFM 2.5 A股单支 | [hf.space](https://1348122919qqcom-timesfm-moirai.hf.space) |

---

## 数据链路

```
K线:     新浪全球期货 → Actions 08:00 → csv.gz → Chronos排名 → JSON + Supabase
Moirai:  商品K线 → Actions 11:00 → Moirai-2 → moirai_ranking.json
Kronos:  新浪A股 → Actions 16:30 → Kronos-sm → ranking.json
情报:    华尔街见闻 → Actions 21:00 → DeepSeek → RSS → Feedly + Space
TimesFM: 新浪A股全量 → Actions 22:00 → TimesFM 2.5 → 全量+精选双JSON
```

### 单支预测数据源

| 模型 | 标的 | 数据源 | 周期 |
|------|------|--------|------|
| Chronos-2 | 商品 | GitHub csv.gz (Actions 08:00更新) | 全量日线 |
| Kronos-sm | A股 | 新浪API datalen=400 (实时) | 1.5年 |
| Moirai-2 | 商品 | GitHub csv.gz (每次下载) | 全量日线 |
| TimesFM 2.5 | A股 | 新浪API datalen=400 (实时) | 1.5年 |

---

## 工作流时间线

```
08:00  K线+Chronos  (~10min)
11:00  Moirai       (~1min)
16:30  Kronos       (~3h)
21:00  情报          (~2min)
22:00  TimesFM      (~20min, 休市自动跳过K线)
```

互相不打架，文件不重叠。

---

## 模型经验

### TimesFM 2.5
- Space: transformers版 (兼容HF) | Actions: timesfm PyPI包 (compile()快5倍)
- 批量: 200只/批, ~38秒/批
- 5207只全量约17分钟
- 128步→30d(22)/60d(44)/128d(128)

### Moirai-2
- API: `uni2ts.model.moirai2` + `create_predictor()` + GluonTS
- 100步→7d/14d/30d/60d/90d
- Context 1680, 512可跑

### Chronos-2
- 30步→7d/14d/30d
- 读本地csv.gz缓存

### Kronos-small
- 30步→30天预测
- 逐只串行, 999只需3小时

---

## 数据源

| | 新浪全球期货 | 新浪A股 |
|------|------------|--------|
| 域名 | stock2.finance.sina.com.cn | money.finance.sina.com.cn |
| 返回 | JSONP | JSON |
| 数据量 | 全量~2500行 | datalen=N |

---

## Space优化记录

- 去所有emoji图标
- TimesFM单支去天数选择，一次输出30d/60d/128d
- 目标价追踪删序号列
- 启动优化: gr.HTML初始值改占位，切标签/点刷新加载
- 2026-06-30精简: 去排名表/情报标签/目标价追踪，只留单支预测

---

## 核心教训

1. 推送前必须征得用户同意
2. timesfm包在Actions快、transformers在Space稳
3. 新模型必须查官方文档验证API
4. git add 先于 git pull
5. Actions runner数据不持久
6. 两个Space隔离，互不影响
7. yfinance不可靠，已全面替换新浪
8. 全量K线tail(600)控制100MB
9. 连续200只无新数据=休市跳过
10. 沟通文档保持最新
