# tv-signals · 大宗商品 & A股 AI情报系统

> 每日自动采集 + DeepSeek AI 分析 + 精选推送 Feedly  
> 零服务器 · 零月费 · 全自动

---

## 整体链路

```
华尔街见闻 API（商品/宏观/A股/外汇 4频道）
        │
        ▼ 每天北京时间 21:00
GitHub Actions（免费云端）
        │
        ▼ Python 脚本
DeepSeek API（deepseek-chat）
        │
        ▼ git push
GitHub Pages（免费）
        │
        ▼ RSS Feed
Feedly（你的阅读终端）
```

---

## 追踪标的

| 商品 | 代码 | A股关联 |
|------|------|---------|
| 黄金 | GC=F / XAUUSD | 山东黄金、紫金矿业 |
| 白银 | SI=F / XAGUSD | — |
| 原油 | CL=F | 中国石油、中国石化 |
| 美铜 | HG=F | 紫金矿业、江西铜业 |
| 伦铝 | AH=F | 云铝股份、中国铝业 |
| 豆粕 | ZM=F | 饲料板块 |
| A股 | 宏观政策 + 行业板块 + 个股信号 | 全市场 |

---

## 每篇文章长什么样

Feedly 里看到的标题格式：

```
[★★★★🔴] 现货黄金跌超1.6%，日内跌幅扩大
[★★★★🟢] 交易员提高对美联储降息押注
[★★★🟡] 国际油价短线下跌，报道称中东停火谈判进展
```

点进去看到 DeepSeek AI 生成的结构化摘要：

- **摘要**：50字中文核心信息
- **情绪**：🔴利空 / 🟡中性 / 🟢利好，带评分
- **关联商品**：品种代码（GC=F、CL=F...）
- **关联A股**：受影响个股或板块
- **分类**：供应中断 / 库存变化 / 政策变动 / 地缘政治...
- **可信度**：根据信息来源权威性评级

---

## 目录结构

```
tv-signals/
├── feeds/
│   ├── commodities.xml    大宗商品精选情报
│   └── a-stocks.xml       A股精选情报
├── scripts/
│   └── fetch_feeds.py     核心采集+AI分析脚本
├── data/
│   ├── processed_urls.json   去重索引
│   └── signal_log.json       信号日志
├── .github/workflows/
│   └── daily-signals.yml     GitHub Actions 定时触发
├── docs/                   项目文档
└── requirements.txt        Python 依赖
```

---

## 系统工作流程

### 每天 21:00 自动执行：

1. **采集** — 从华尔街见闻 API 拉取 4 个频道（商品、宏观、A股、外汇），约 200 条
2. **过滤** — 关键词匹配黄金/白银/原油/铜/铝/豆粕/A股
3. **去重** — SHA1 URL 哈希，已处理过的跳过
4. **AI 分析** — DeepSeek 深度分析每篇文章，输出：
   - 中文摘要（50字）
   - 情感打分（-1 到 +1）
   - 影响力评级（1-5★）
   - 关联品种代码
   - 关联A股标的
   - 分类标签
   - 可信度评分
5. **生成 RSS** — 筛选 ≥2★ 的文章，生成精选 XML
6. **发布** — git push 到 GitHub Pages，Feedly 自动更新

---

## 部署

### 前置条件

1. DeepSeek API Key：https://platform.deepseek.com/api_keys
2. GitHub 公开仓库（已就绪：`chenheping1974/tv-signals`）

### 步骤

1. **Fork 本仓库** 或直接使用
2. **设置 Secret**：GitHub → Settings → Secrets → Actions → `DEEPSEEK_API_KEY`
3. **启用 Pages**：Settings → Pages → Source: `main` → `/ (root)` → Save
4. **手动测试**：Actions → 每日AI情报 → Run workflow
5. **Feedly 订阅**：添加以下 2 个 URL
   ```
   https://chenheping1974.github.io/tv-signals/feeds/commodities.xml
   https://chenheping1974.github.io/tv-signals/feeds/a-stocks.xml
   ```

---

## 成本

| 组件 | 月费 |
|------|------|
| GitHub Actions | $0（公开仓库无限） |
| GitHub Pages | $0 |
| DeepSeek API | ~$0（免费额度内，约 1,000 tokens/天） |
| 华尔街见闻 API | $0（公开 API） |
| Feedly | 已有 |

**总计每月支出：$0**

---

## 扩展计划

系统预留了以下扩展接口：

- **金十数据 API**：找到可用端点后加入
- **TradingView MCP 交叉验证**：高分文章触发技术面共振检测
- **每日简报**：自动生成盘后交易简报
- **更多信源**：EIA 原油周报、CFTC 持仓报告、上期所仓单日报
