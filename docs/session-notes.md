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
- 4条件筛选：ST排除 / 科创板北交所排除 / 市值>80亿 / 成交额>1亿 → ~1000只
- 每周一本地 `python scripts/screen_pool.py` 重筛+下数据+推仓库
- 日常 GitHub Actions (16:30) 自动增量+预测

### 数据流
```
Mac本地(每周)：screen_pool.py → 腾讯筛池 → 新浪下OHLCV → git push
Actions(每天)：读 OHLCV → 抽查10只判断有无新数据 → 增量追加 → Kronos → git push
Space(随时)：读 ranking.json → 榜单
```

### Kronos-small
- 24.7M, MIT, NeoQuasar/Kronos-small
- 必传：x_timestamp(Series) + y_timestamp(Series)
- 日期解析：ISO8601格式

## 预测平台 (HF Space)

### 标签
| 标签 | 功能 | 模型 |
|------|------|------|
| ⚡ 综合 | 预测+AI判断+情报同屏 | Chronos-2+DeepSeek |
| 🏭 商品 | 6品种预测+排名 | Chronos-2 |
| 🏦 A股 | 任意输入+Top50榜单 | Kronos-sm |
| 📡 情报 | RSS精选 | — |

### 商品品种
现货黄金/白银、国际原油、COMEX铜、LME铝、豆粕

### A股功能
- 🏆 Top 50 榜单：左1-25，右26-50，红色渐变
- 任意输入：5528条名→码映射
- 实时预测+公告+DeepSeek
- 双数据源：Yahoo→新浪备用

### 数据缓存
- 商品：Space本地CSV缓存10年，增量更新
- A股：Yahoo实时+新浪备用

## 核心教训
1. 先验证数据源→设计→代码
2. 查API文档再调参
3. SSH/Git优先
4. 用官方requirements.txt
5. 推送前校验
