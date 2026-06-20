# 项目沟通笔记

---

## 2026-06-19 — 情报系统搭建

### 项目目标
构建面向大宗商品和中国A股的 AI 驱动 RSS 信息系统。核心标的：黄金、白银、原油、美铜、伦铝、豆粕、A股。

### 关键决策
| 决策 | 结论 |
|------|------|
| 输出方式 | 精选 RSS Feed（方案A）→ GitHub Pages |
| 编排引擎 | Make → 放弃 → GitHub Actions |
| AI 引擎 | Claude API → DeepSeek（中文强、便宜） |
| 信源 | RSSHub → 放弃（403）→ 华尔街见闻 API 直连 |
| 推送终端 | Feedly（3 Board：商品/A股/简报） |
| 运行频率 | 每天 21:00 UTC+8 |
| 成本 | $0/月 |

### 放弃的方案
- **Make**：免费版 1,000 ops/月不够，GUI 配置复杂
- **RSSHub 公共实例**：GitHub Actions 机房 IP 被 Cloudflare 403 拦截
- **RSSHub 自部署**：Railway/Render 部署失败
- **金十数据 API**：502；**财联社 API**：未找到可用端点

### 最终架构
```
华尔街见闻 API（commodity/global/a_stock/forex 4频道）
    → GitHub Actions（每天 21:00）
    → Python 脚本（采集→过滤→去重→DeepSeek分析→生成RSS）
    → GitHub Pages
    → Feedly
```

### 关键Bug修复
- **A股 Feed 只有1条**：DeepSeek 每批 idx 从0编号，多批覆盖。改为顺序配对 `articles[i] ↔ analysis_results[i]`
- **A股混入商品**：双把关（来源必须是 a_stock 频道 + AI 确认关联A股），A股 Feed 不合并历史
- **评分阈值**：商品 ≥2★，A股 ≥1★
- **Feedly 缓存**：GitHub Pages 更新后 Feedly 2-6 小时延迟，Unfollow+Follow 强制刷新

---

## 2026-06-20 — Chronos-2 + TimesFM 预测模型

### 讨论
对比 Chronos-2 (Amazon, 120M) vs TimesFM 2.5 (Google, 200M)。选择 Chronos-2 —— 多变量 group attention 适合商品联动场景，Apache 2.0 免费，CPU 可跑。

### 部署：Hugging Face Spaces Gradio 应用
- 踩坑：Factory Rebuild 卡死 Node.js 安装（网络问题）；
  pydantic 版本冲突；SSR 代理连不上；
  Chronos-2 DataFrame 格式要求（timestamp/target/item_id 三列）；
  时区问题（`pd.to_datetime(utc=True).tz_localize(None)`）；
  频率推断（加 `freq='B'` 参数）；
  pandas iloc 索引歧义；
  Plotly 用 `gr.Plot` 不显示 → `gr.Plotly`
- 最终成功：`1348122919qqcom-commodity-forecast.hf.space`

### 架构
```
用户浏览器
    → HF Spaces (Gradio, Free CPU)
    → Yahoo Finance (价格数据)
    → Chronos-2 (120M, 预测)
    → DeepSeek API (综合判断)
    → GitHub Pages RSS (情报)
    → 返回：交互式图表 + AI判断 + 新闻
```

### 功能
- 4个标签：综合看盘 / 商品预测（7品种） / A股预测（自选+任意代码） / 情报（RSS读取）
- Plotly 交互式图表（滚轮缩放、拖拽、悬停）
- 综合看盘：Chronos-2预测 + 关联新闻 + DeepSeek交叉判断
- 配色：Ocean 深海科技风

### SSH 配置
- HF Spaces 本质是 Git 仓库：`git@hf.co:spaces/1348122919qqcom/commodity-forecast`
- 添加 SSH Key 后直接 `git push`，无需手动上传

### 用户偏好
- 最优方案优先，拒绝低效试错
- 部署类优先配 SSH/Git，不做手动上传
- 先校验再推送

---

## 两个系统总览

| | tv-signals (情报) | chronos-forecast (预测) |
|------|------|------|
| 功能 | 新闻→AI分析→RSS | 价格→Chronos-2预测→图表 |
| AI | DeepSeek | Chronos-2 + DeepSeek |
| 部署 | GitHub Actions | HF Spaces |
| 输出 | Feedly | 网页 |
| 频率 | 每天 21:00 | 随时打开 |
| 费用 | $0 | $0 |

## 待扩展
- 两个系统整合：预测结果标注到 RSS Feed
- TradingView MCP 交叉验证
- 更多信源（CFTC、EIA、上期所）
