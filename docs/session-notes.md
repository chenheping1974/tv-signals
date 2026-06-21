# 项目沟通笔记

## 系统总览

两个子系统协同工作：

| | tv-signals（情报） | chronos-forecast（预测） |
|------|------|------|
| 功能 | 新闻→AI 分析→RSS Feed | 价格→AI 预测→交互图表 |
| AI 引擎 | DeepSeek | Chronos-2 + Kronos-small + DeepSeek |
| 部署 | GitHub Actions | HuggingFace Spaces |
| 输出 | Feedly | 网页 |
| 频率 | 每天 21:00 | 随时打开 |
| 费用 | $0 | $0 |

---

## 2026-06-19 — 情报系统搭建

### 关键决策
- 编排引擎：Make → 放弃 → GitHub Actions
- AI 引擎：Claude → DeepSeek（中文强、$0）
- 信源：RSSHub → 放弃（403）→ 华尔街见闻 API 直连
- 输出：GitHub Pages RSS → Feedly

### 最终架构
```
华尔街见闻 API → GitHub Actions (21:00) → DeepSeek → RSS XML → GitHub Pages → Feedly
```

### 关键 Bug
- A股 Feed 只 1 条：DeepSeek idx 多批覆盖 → 顺序配对修复
- A股混入商品：双把关（来源频道 + AI 确认）
- Feedly 缓存延迟 2-6h

---

## 2026-06-20 — Chronos-2 预测模型部署

### HF Space 踩坑
- pydantic 版本冲突、SSR 模式、端口环境变量
- DataFrame 格式：timestamp/target/item_id
- 网络：GitHub Actions US 机房被 rsshub.app Cloudflare 403

### 成功部署
- Chronos-2 商品预测 7 品种
- Plotly 交互图表、Ocean 深色主题
- DeepSeek 综合判断

---

## 2026-06-20~21 — Kronos-small A 股选股系统

### 股票池
- 数据源：akshare → 新浪财经 API → 腾讯财经 API
- 筛选：四条件（ST 排除/科创板北交所/市值>80亿/成交额>1亿）→ 873 只
- 后续扩展到 4361 只全市场

### Kronos 批量预测
- 模型：NeoQuasar/Kronos-small (24.7M, MIT)
- API 要求：x_timestamp/y_timestamp 必须 Series，必须传 y_timestamp
- 每只 ~3 秒，873 只 ~40 分钟，4361 只 ~3.5 小时
- 断点续跑防失败

### HF Space A 股标签页
- 🏆 每日选股 Top 50（左 1-25，右 26-50，红色系渐变）
- 任意股票输入：6 位代码或股票名（5528 条映射）
- Kronos-small 实时预测 + DeepSeek 综合判断
- 东方财富个股公告 API 接入
- 双数据源：Yahoo Finance + 新浪财经备用

### 数据流
```
本地 Mac（一次性）：
  akshare 股票池 → 新浪财经 OHLCV → ohlcv.csv.gz (21MB) → git push

GitHub Actions（每天 16:30）：
  读 ohlcv.csv.gz → 增量追加当日 → Kronos 批量预测
  → ranking.json → git push → GitHub Pages

HF Space（随时）：
  读 ranking.json → 榜单展示 + 个股实时预测
```

### 核心教训
- 先验证数据源连通性，再设计流程，最后写代码
- 先查文档再调用 API，不猜测参数格式
- 部署优先配 SSH/Git
- 简单错误积累导致大量重复工作（import 残留、变量名不匹配、pandas or 歧义）
