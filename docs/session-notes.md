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

## 2026-06-22 数据源审计 & 商品数据方案

### 问题发现

排查大宗商品数据链路，发现以下问题：

| 功能 | 当前数据源 | 实测结果 |
|------|-----------|----------|
| 大宗商品预测（Chronos） | yfinance `period="10y"` | 6品种全部限流失败 |
| A股单支预测（Kronos） | yfinance → fallback 新浪 | yf先挂2.7s再走新浪0.3s |
| A股排行榜 ranking.json | 新浪财经（Actions） | ✅ 稳定 |

### 数据源实测

**yfinance（本地）：**
- GC=F, SI=F, CL=F, HG=F, AH=F, ZM=F 全部 `YFRateLimitError`
- A股 601899.SS 同样限流
- 结论：6个请求就触发封禁，不可靠

**新浪全球期货 API：**
```
GET stock2.finance.sina.com.cn/futures/api/jsonp.php/
    ?symbol=GC&_=2026_6_22
    /GlobalFuturesService.getGlobalFuturesDailyKLine
```

| 商品 | 代码 | 数据量 | 起始 |
|------|------|--------|------|
| 黄金 | GC | 2,589 | 2016-06 |
| 白银 | SI | 2,589 | 2016-06 |
| 原油 | CL | 7,687 | 1996-06 |
| 美铜 | HG | 2,590 | 2016-06 |
| 伦铝 | AHD | 2,537 | 2016-06 |
| 豆粕 | SM | 2,542 | 2016-06 |

- 10次快速连续请求全部200，无限流
- OHLC齐全，成交量除伦铝外为0（不影响价格预测）
- AKShare底层同源，社区验证多年

**两个新浪 API 的区别：**

| | 全球期货 API | A 股 API |
|------|-------------|---------|
| 域名 | `stock2.finance.sina.com.cn` | `money.finance.sina.com.cn` |
| 路径 | `/futures/api/jsonp.php/` | `/quotes_service/api/json_v2.php/` |
| 服务 | `GlobalFuturesService.getGlobalFuturesDailyKLine` | `CN_MarketData.getKLineData` |
| 返回格式 | **JSONP**（需去包装） | **纯 JSON** |
| 参数 | `symbol=GC` | `symbol=sh601899&scale=240&datalen=400` |
| 数据量控制 | 无分页参数，返回全量 | `datalen=N` 可控 |

⚠️ 不是同一个 API，调用方式和解析逻辑都不同，不能直接复用 A 股现有代码。

**新浪 A 股 API（已在用）：**
- 端点：`money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData`
- datalen=400: 0.3s，稳定
- 排行榜 `stock_ranking.py` 早已纯新浪

### 商品数据更新机制现状

```
用户点击"预测商品"
  → 检查 data_{symbol}.csv 缓存
    → ≤8h: 直接用
    → >8h 或无: yfinance 增量/全量拉 → 存缓存
  → 喂 Chronos-2
```

问题：
1. 完全被动触发，无人点就不更新
2. 缓存路径相对，Space重启全丢 → 重下10年 → 触发限流
3. 排行榜串行6品种，任一个挂就缺结果
4. yfinance 为唯一数据源，实测全部限流

### 推荐方案（待明天确认）

1. **商品数据换源**：yfinance → 新浪全球期货 API（和A股同体系）
2. **Actions 定时更新**：每天拉6品种增量 → push `commodities_ohlcv.csv.gz`
3. **Space 读缓存**：从 GitHub raw 下载到 `/home/user/`，防重启丢失
4. **A股单支预测去 yf**：砍掉 yfinance 分支，纯新浪

### A股单支预测数据链路

```
用户点预测 → try_yfinance(period="1y") → 失败(2.7s)
           → fallback try_sina(datalen=400) → 成功(0.3s)
           → 取后512根日线 → Kronos预测
```

不存缓存，每次实时拉。yf分支纯浪费3秒。

## 2026-06-23 数据源全链路修复

### 已修复项

| # | 问题 | 修复 | 涉及文件 |
|---|------|------|----------|
| 1 | 选股OHLCV更新条件off-by-one | `data_date < today` | `stock_ranking.py:85` |
| 2 | 商品数据源yfinance限流 | 新浪全球期货API | `update_commodities.py` (新增) |
| 3 | 商品无定时更新 | Actions每天08:00北京 | `.github/workflows/commodities-ohlcv.yml` |
| 4 | 商品预测直接调yf | Space读共享csv.gz，冷启动从GitHub下载 | `app.py:predict()` |
| 5 | A股单支预测yf浪费3s | 纯新浪，移除yfinance分支 | `app.py:predict_kronos_stock()` |

### 当前数据源全貌

| 功能 | 数据源 | 更新方式 |
|------|--------|----------|
| A股排行榜OHLCV | 新浪财经 | Actions 16:30 增量 |
| 商品预测OHLCV | 新浪全球期货 | Actions 08:00 全量 |
| A股单支预测 | 新浪财经 | 用户点击实时拉 |
| 商品/A股情报 | 华尔街见闻 | Actions 21:00 |

### 商品数据链路（新）

```
Actions(每天08:00北京)
  → 新浪全球期货API(6品种全量日线)
  → commodities_ohlcv.csv.gz
  → git push

Space冷启动
  → GitHub raw下载 → /home/user/commodities_ohlcv.csv.gz

Space预测
  → 读/home/user/缓存 → 按symbol筛选 → Chronos-2
```
