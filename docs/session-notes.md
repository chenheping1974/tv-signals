# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 | 输出 |
|------|------|------|------|------|
| 📰 情报 | 商品+A股新闻 | DeepSeek | 每天 21:00 | Feedly |
| 🏆 选股 | A股横截面排序 | Kronos-small | 每天 16:30 | ranking.json |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | 随时 | HF Space |
| 💰 成本 | $0/月 | | | |

## 情报系统

华尔街见闻 API → GitHub Actions (21:00) → DeepSeek → RSS → GitHub Pages → Feedly + Space 情报页

## 选股系统

### 股票池
- 4条件：ST/科创北交/市值>80亿/成交额>1亿 → 999只
- 每周一 `python scripts/screen_pool.py` 重筛（Mac本地）
- 每天 `python scripts/update_ohlcv.py` 增量（Mac本地，新浪3分钟）

### 数据流
```
Actions(每天16:30)：
  读OHLCV → 数据旧了? → 新浪增量(datalen=10,快) → Kronos 999只(~3h)
  → ranking.json → artifact+push
  排名已最新? → 跳过

Space(A股)：读ranking.json → Top50 + 目标价追踪
Space(商品)：Chronos-2 + 排名缓存 + DeepSeek
```

### Cron修复
- `30 8 * * 1-5` 从未触发 → `30 8 * * 1,2,3,4,5` 显式写法
- 证明：daily-signals (`0 13 * * *`) 正常触发 2次

### yfinance踩坑
- 批量下载 `database is locked`（SQLite多线程冲突）
- 逐只下载在Actions限流
- **最终方案**：新浪财经增量（datalen=10，快速，已验证Actions可通）

## 预测平台 (HF Space)

### 三个标签
| 标签 | 功能 |
|------|------|
| 🏭 商品预测 | Chronos-2 + DeepSeek + 30天排名(缓存) |
| 🏦 A股预测 | Kronos-sm + Top50 + 目标价追踪 |
| 📡 情报 | 左商品右A股，一键刷新 |

### 持久化
- `/home/user/targets.json` — 休眠重启不丢
- 商品排名缓存同文件
- 标签select自动刷新

### 目标价追踪
- 30天+90天目标价，从涨跌幅反算
- 序号删除，标签切换自动显示
- 代码推不丢（独立于Git目录）

## 核心教训
1. 先验证数据源 → 设计 → 代码
2. 用已验证过的数据源，不跳来跳去
3. 全局替换必查影响范围
4. Cron显式写，避免范围格式解析失败
5. yfinance在Actions多问题，新浪稳定
6. 增量只拉少量数据（datalen=10），不全量重下
