# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 数据源 | 触发 | 输出 |
|------|------|------|--------|------|------|
| 📰 情报 | 商品+A股新闻精选 | DeepSeek | 华尔街见闻 API | 每天 21:00 | Feedly RSS |
| 🏆 选股 | A股横截面排序 | Kronos-sm | 新浪财经 OHLCV | 每天 16:30 | ranking.json |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | Yahoo/Sina 双源 | 随时 | HF Space 网页 |
| 💰 成本 | $0/月 | | | | |

## 2026-06-19 — 情报系统

### 关键决策
- 编排：Make → GitHub Actions（免费无限）
- AI：Claude → DeepSeek（中文强、$0）
- 信源：RSSHub(403) → 华尔街见闻 API
- 输出：GitHub Pages RSS → Feedly

### 关键修复
- A股 Feed idx 多批覆盖 → 顺序配对
- A股混商品 → 双把关(频道+AI确认)
- Feedly 缓存 2-6h

## 2026-06-20 — Chronos-2 预测平台

### HF Space 部署
- pydantic 冲突、SSR 代理、端口环境变量
- Chronos-2 DataFrame 格式：timestamp/target/item_id
- Plotly 交互图表、Ocean 深色主题
- Gradio 6.x：gr.Plot 非 gr.Plotly

### 预测功能
- 商品 7 品种 Chronos-2 预测
- A股 Kronos-small 实时预测 + DeepSeek 综合判断
- 双数据源：Yahoo + 新浪备用
- 个股公告：东方财富 API

## 2026-06-21 — A股选股系统

### 股票池
- 全市场 4699 只（排除科创板/北交所/ST）
- 可用 OHLCV 数据：4365 只（93%）
- 缺失 334 只：上市不足 3 月的新股，数据<60天
- 每日自动检测新股，数据够 60 天自动纳入

### Kronos 批量预测
- 模型：NeoQuasar/Kronos-small (24.7M, MIT)
- 必传参数：x_timestamp(Series) + y_timestamp(Series)
- 每只 ~3 秒，4365 只 ~3.5 小时
- 断点续跑防失败

### HF Space A 股标签
- 🏆 Top 50 榜单：左 1-25，右 26-50，红色渐变
- 任意股票输入：5528 条名→码映射
- Kronos-sm 实时预测 + 公告 + DeepSeek
- 刷新榜单自动更新下拉框

### 数据流
```
Mac 本地（一次性）：akshare 池 → 新浪/腾讯 OHLCV → ohlcv.csv.gz (21MB)

GitHub Actions（每天 16:30）：
  读 OHLCV → 增量追加 → Kronos 批量预测 → ranking.json → git push

HF Space（随时）：读 ranking.json → 榜单 + 个股预测
```

### 数据源验证
- 新浪财经 K线 API ✅ (Mac + GitHub Actions)
- 腾讯财经行情 API ✅
- 东方财富公告 API ✅
- akshare stock_info_a_code_name ✅

### 核心教训
1. 先验证数据源 → 设计流程 → 写代码
2. 先查文档再调 API
3. 部署优先配 SSH/Git
4. 校验后再推送运行
5. 每次改动注明改了哪里
