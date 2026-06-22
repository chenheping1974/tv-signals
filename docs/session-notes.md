# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 | 输出 |
|------|------|------|------|------|
| 📰 情报 | 商品+A股新闻 | DeepSeek | 每天 21:00 | Feedly |
| 🏆 选股 | A股横截面排序 | Kronos-small | 每天 16:30 | ranking.json |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | 随时 | HF Space |
| 💰 成本 | $0/月 | | | |

## 情报系统

华尔街见闻 API → GitHub Actions (21:00) → DeepSeek → RSS → GitHub Pages → Feedly

## 选股系统

### 股票池
- 4条件：ST/科创北交/市值>80亿/成交额>1亿 → 999只
- 每周一 `python scripts/screen_pool.py` 重筛+下数据

### 数据流
```
Actions(每天16:30)：抽查10只增量 → Kronos 999只 → ranking.json → artifact+push
Space(A股)：读 ranking.json → Top50榜单 | 个股+公告+DeepSeek
Space(商品)：10年CSV缓存 → 增量 → Chronos-2
```

### Kronos-small
- 24.7M, MIT, NeoQuasar/Kronos-small
- 必传：x_timestamp(Series) + y_timestamp(Series)
- ISO8601, 官方 requirements.txt
- 断点+artifact保底

## 预测平台 (HF Space)

### 三个标签

| 标签 | 功能 |
|------|------|
| 🏭 商品预测 | Chronos-2 + DeepSeek + 30天排名(缓存) |
| 🏦 A股预测 | Kronos-sm + Top50 + 目标价追踪 |
| 📡 情报 | 左商品右A股，一键刷新 |

### A股目标价追踪
- 📌 保存 → 30天+90天目标价 → 持久化 `/home/user/targets.json`
- 🗑️ 序号删除
- 标签切换自动显示
- 休眠/重启不丢，Factory rebuild 才丢

### 商品排名缓存
- 标签打开读缓存（同天秒显）
- 刷新按钮重算+覆盖缓存
- 同文件持久化

### 技术特性
- SSH 推送 + 自动构建
- Gradio 登录保护
- yf_dl 兼容 Yahoo v2
- 商品 10年 CSV 缓存
- 标签 select 事件自动刷新

## 核心教训
1. 先验证→设计→代码
2. 查文档再调参
3. 全局替换慎用
4. 推送前校验
5. 持久化路径先测通
