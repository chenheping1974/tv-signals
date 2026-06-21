# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 数据源 | 触发 | 输出 |
|------|------|------|--------|------|------|
| 📰 情报 | 商品+A股新闻精选 | DeepSeek | 华尔街见闻 API | 每天 21:00 | Feedly RSS |
| 🏆 选股 | 全市场横截面排序 | Kronos-small | 新浪财经 OHLCV | 每天 16:30 | ranking.json |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | Yahoo/新浪/东方财富 | 随时 | HF Space |
| 💰 成本 | $0/月 | | | | |

## 完整架构

```
情报系统：
  华尔街见闻 API → GitHub Actions (21:00) → DeepSeek → RSS XML → GitHub Pages → Feedly

选股系统：
  新浪财经 OHLCV → GitHub Actions (16:30, 两批并行) → Kronos-sm → ranking.json
  → GitHub Pages → HF Space 榜单

预测平台 (HF Space)：
  Chronos-2 (商品) + Kronos-sm (A股) + DeepSeek 综合判断
  + 东方财富个股公告 + 新浪/雅虎双源 OHLCV
```

---

## 2026-06-19 — 情报系统搭建

### 关键决策
- 编排：Make → GitHub Actions
- AI：Claude → DeepSeek
- 信源：RSSHub(Cloudflare 403) → 华尔街见闻 API 直连
- 输出：GitHub Pages RSS → Feedly

### 关键修复
- A股 idx 多批覆盖 → 顺序配对
- A股混商品 → 双把关(频道+AI确认)
- Feedly 缓存延迟 2-6h

---

## 2026-06-20 — Chronos-2 预测平台 + Kronos 选股

### HF Space 部署踩坑
- pydantic 版本冲突、SSR 代理、端口环境变量
- Gradio 6.x：gr.Plot 非 gr.Plotly
- 模型加载懒加载避免启动超时
- SSH 配置：git@hf.co 免手动上传

### A股选股系统
- 股票池：akshare → 新浪/腾讯 API 交叉验证 → 4365 只(93% 覆盖)
- 缺失 334 只：上市不足 3 月，每日自动检测纳入
- 数据格式：timestamp/target/item_id 三列，pd.to_datetime(format='mixed')
- Kronos 必传：x_timestamp(Series) + y_timestamp(Series)

### 并行优化
- 4365 只单 Job ~7h 超 6h 限制 → 两批并行各 ~3.5h
- batch-0 (前 2200) + batch-1 (后 2165) 并行 → merge 合并
- 依赖：Kronos 官方 requirements.txt

### Space A股标签功能
- 🏆 Top 50 榜单：左 1-25，右 26-50，红色渐变
- 任意输入：5528 条名→码映射，支持代码或名称
- 实时预测：Kronos-sm + 东方财富个股公告 + DeepSeek 综合判断
- 双数据源：Yahoo → 新浪备用
- 刷新榜单自动更新下拉框

## 核心教训
1. 先验证数据源连通性 → 设计流程 → 写代码
2. 先查 API 文档再调参数
3. SSH/Git 优先，不手动上传
4. 推送前本机校验
5. 尽量避免 import 残留、变量名不匹配等低级错误
6. 依赖用官方 requirements.txt，不手动猜包名
