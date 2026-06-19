# tv-signals · 大宗商品 & A股 AI情报系统

> 每日自动采集 + DeepSeek 人工智能分析 + 精选推送 Feedly
> 零服务器 · 零月费 · 完全自动化

---

## 整体链路

```
RSSHub公共实例 (免费)    Make云端 (免费版)      DeepSeek API (~$0/月)
       │                      │                      │
  30+信源→RSS           定时21:00触发          deepseek-chat模型
       │                  批量AI分析                  │
       └───────────────────┼──────────────────────────┘
                           │
                    GitHub Pages (免费)
                           │
                    2个精选RSS Feed
                    · commodities.xml
                    · a-stocks.xml
                           │
                        Feedly
                    (你的阅读终端)
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

## 目录结构

```
tv-signals/
├── feeds/
│   ├── commodities.xml    大宗商品精选情报
│   └── a-stocks.xml       A股精选情报
├── briefs/                每日简报存档（自动生成）
├── docs/                  配置文档
│   ├── rss-sources.md     信源清单
│   ├── deepseek-prompt.md AI Prompt 模板
│   └── make-scenario.md   Make 配置
└── README.md
```

---

## 部署步骤

### 第1步：Fork 本仓库到你的 GitHub

```
1. 点击 Fork
2. Settings → Pages → Source: main branch, / (root) → Save
3. 等待 1-2 分钟，访问 https://{你的用户名}.github.io/tv-signals/feeds/commodities.xml
   确认能看到 XML 内容
```

### 第2步：获取 API Key

| 服务 | 地址 | 费用 |
|------|------|------|
| DeepSeek | https://platform.deepseek.com → API Keys | 新用户有免费额度 |
| GitHub Token | https://github.com/settings/tokens → Generate new token (classic) → 勾选 `repo` | 免费 |

### 第3步：验证 RSSHub 路由

在浏览器依次打开以下 5 个地址，确认返回 RSS XML：

```
https://rsshub.app/smm/news
https://rsshub.app/cls/telegraph
https://rsshub.app/wallstreetcn/news
https://www.eia.gov/rss/petroleum.xml
https://rsshub.app/cftc/cot
```

如果某个路由不能用，去 https://docs.rsshub.app 搜索替代路由。

### 第4步：配置 Make Scenario

打开 [docs/make-scenario.md](docs/make-scenario.md)，按照逐步骤配置。

需要填入的变量：
- `{DEEPSEEK_API_KEY}` → DeepSeek 后台获取
- `{GITHUB_TOKEN}` → GitHub 设置页获取
- `{你的用户名}` → 你的 GitHub 用户名

### 第5步：运行测试

在 Make 里点 "Run once" → 观察每个模块输出 → 确认无报错 → 启用 Schedule。

### 第6步：Feedly 订阅

打开 Feedly → Add Content → 输入以下 2 个 URL：

```
https://{你的用户名}.github.io/tv-signals/feeds/commodities.xml
https://{你的用户名}.github.io/tv-signals/feeds/a-stocks.xml
```

在 Feedly 中创建 3 个 Board：
- 🥇 大宗商品 ← 订阅 commodities.xml
- 📊 A股 ← 订阅 a-stocks.xml  
- 📋 每日简报 ← Feedly 直接看 /briefs/ 目录

---

## 每篇文章长什么样

Feedly 里看到的标题格式：

```
[★4🔴] EIA原油库存意外大降810万桶，远超预期
[★5🟢] 央行超预期降准50BP，释放长期资金约1万亿
[★3🟡] LME铜库存连续第3日增加，但增幅收窄
[★1⚪] 某分析师认为黄金年内将突破3000美元
```

点进去看到 AI 生成的摘要、情感评分、关联标的。

---

## 成本

| 组件 | 月费 |
|------|------|
| RSSHub | $0（公共实例） |
| Make | $0（免费版，交易日内运行） |
| DeepSeek API | ~$0（免费额度内） |
| GitHub Pages | $0 |
| Feedly | 已有 |

**总计每月支出：$0**

---

## 扩展

系统预留了 TradingView 交叉验证接口。后续在 Make 中加入：

```
高分文章 → HTTP → TradingView API
  → 查技术面（RSI/布林带/成交量）
  → 返回共振结果
  → 标注到文章标题：[★5🔴 技术共振] ...
```
