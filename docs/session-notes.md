# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 | 输出 |
|------|------|------|------|------|
| 📰 情报 | 商品+A股新闻精选 | DeepSeek | 每天 21:00 | Feedly |
| 🏆 选股 | A股横截面排序 | Kronos-small | 每天 16:30 | ranking.json |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | 随时 | HF Space |
| 💰 成本 | $0/月 | | | |

## 情报系统

华尔街见闻 API → GitHub Actions (21:00) → DeepSeek → RSS → GitHub Pages → Feedly

## 选股系统

### 股票池
- 4条件：ST排除 / 科创板北交所 / 市值>80亿 / 成交额>1亿 → ~1000只
- 每周一 Mac 本地 `python scripts/screen_pool.py` 重筛+下数据+推仓库
- 日常自动跑忽略池子变动

### 数据流
```
Mac（每周）：screen_pool.py → 腾讯财经筛池 → 新浪财经 OHLCV → git push

Actions（每天16:30）：读 OHLCV → 增量追加 → Kronos 预测 → ranking.json → git push

Space（随时）：读 ranking.json → 榜单
```

### 技术细节
- Kronos-small：NeoQuasar/Kronos-small, 24.7M, MIT
- 必传参数：x_timestamp(Series) + y_timestamp(Series)
- 日期解析：ISO8601（快 5-6 倍）
- 依赖：Kronos 官方 requirements.txt
- 增量更新：先抽查10只有无新数据，无则跳，有则全量

## 预测平台 (HF Space)

### 标签
| 标签 | 功能 | 模型 |
|------|------|------|
| 🔮 综合 | 预测+AI判断+情报同屏 | Chronos-2+DeepSeek |
| 🏭 商品 | 7品种预测 | Chronos-2 |
| 🏦 A股 | 任意输入+Top50榜单 | Kronos-sm |
| 📡 情报 | RSS精选 | — |

### 数据源
- 商品：Yahoo Finance
- A股：Yahoo → 新浪备用
- 公告：东方财富 API
- 名码映射：5528条

## 核心教训
1. 先验证数据源 → 设计流程 → 写代码
2. 查完API文档再调
3. SSH/Git优先，不手动上传
4. 用官方requirements.txt，不猜包名
5. 格式优化先测
