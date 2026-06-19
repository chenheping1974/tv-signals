# 2026-06-19 沟通笔记

## 项目目标

构建一个面向大宗商品和中国A股领域的 AI 驱动 RSS 信息系统。核心追踪标的：黄金、白银、原油、美铜、伦铝、豆粕、A股。

## 需求探索过程

1. **初始想法**：Feedly + Make + RSSHub + Claude API
2. **调整为免费方案**：Make 免费版仅 1,000 ops/月 → 降到每天 1 次采集 → 最终放弃 Make，改用 GitHub Actions
3. **RSSHub 探索**：公共实例 rsshub.app 在用户浏览器可访问，但 GitHub Actions 服务器被 403 封禁
4. **最终方案**：绕过 RSSHub，直接调用华尔街见闻原始 API

## 关键决策

| 决策 | 结论 |
|------|------|
| 输出方式 | 精选 RSS Feed（方案A） |
| RSS 托管 | GitHub Pages（免费） |
| 编排引擎 | GitHub Actions（免费） |
| AI 引擎 | DeepSeek（中文更强，~$0/月） |
| 信源 | 华尔街见闻 API（commodity/global/a_stock/forex 4频道） |
| 推送终端 | Feedly |
| 运行频率 | 每天 21:00（北京时间） |
| TradingView 交叉验证 | 预留扩展接口 |

## 放弃的方案

- **Make**：免费版 ops 不够，配置复杂，频繁退出登录
- **RSSHub 公共实例**：从 GitHub Actions IP 被封（403），从用户浏览器可访问但从 AWS 机器不行
- **RSSHub 自部署**：Railway/Render 部署失败
- **金十数据 API**：502 不可用
- **财联社 API**：未找到可用端点

## 最终架构

```
华尔街见闻 API（商品/宏观/A股/外汇4频道）
        │
        ▼ (每天UTC 13:00 = 北京时间21:00)
GitHub Actions（免费）
        │
        ▼ Python 脚本
DeepSeek API（deepseek-chat）
        │
        ▼ git push
GitHub Pages（免费）
        │
        ▼ RSS Feed
Feedly（用户已有）
```

## 文件结构

```
tv-signals/
├── feeds/
│   ├── commodities.xml    大宗商品精选（≥2★）
│   └── a-stocks.xml       A股精选（≥2★）
├── scripts/
│   └── fetch_feeds.py     核心采集+AI处理脚本
├── data/
│   ├── processed_urls.json   去重索引
│   └── signal_log.json       信号日志
├── .github/workflows/
│   └── daily-signals.yml     GitHub Actions 定时触发
└── requirements.txt
```

## 成本

**$0/月** — 全部组件免费：GitHub Actions（公开仓库无限）、GitHub Pages、DeepSeek（免费额度内）、华尔街见闻 API（公开）。

## 待扩展

- 金十数据（找到可用 API 端点后加入）
- TradingView MCP 交叉验证
- 每日简报自动生成
- A股信源补充
