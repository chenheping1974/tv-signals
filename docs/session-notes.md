# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 | 输出 |
|------|------|------|------|------|
| 📰 情报 | 商品+A股新闻精选 | DeepSeek | 每天 21:00 | Feedly |
| 🏆 选股 | A股横截面排序 | Kronos-small | 每天 16:30 | ranking.json |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | 随时 | HF Space |
| 💰 成本 | $0/月 | | | |

## 情报系统

华尔街见闻 API → GitHub Actions (21:00) → DeepSeek → RSS XML → GitHub Pages → Feedly

## 选股系统

### 股票池
- 4条件筛选：ST/科创板北交所/市值>80亿/成交额>1亿 → ~1000只
- 每周一 Mac 本地 `python scripts/screen_pool.py` 重筛+下数据
- GitHub Actions (16:30)：增量更新 OHLCV + Kronos 预测

### 数据流
```
Mac本地(每周)：screen_pool.py → 腾讯行情筛池 → 新浪财经 OHLCV → git push
Actions(每天)：抽查10只增量 → Kronos 预测 → ranking.json → git push
Space(随时)：读 ranking.json → 榜单 | 实时预测 + 公告 + DeepSeek
Space(商品)：首次 Yahoo 10yr 缓存盘 → 增量 → Chronos-2
```

### Kronos-small
- 24.7M, MIT, NeoQuasar/Kronos-small
- 必传：x_timestamp(Series) + y_timestamp(Series)
- ISO8601 日期格式
- 依赖：Kronos 官方 requirements.txt
- 断点续跑 + artifact 保底

## 预测平台 (HF Space)

### 标签
| 标签 | 功能 | 模型 |
|------|------|------|
| 商品AI预测 | 预测+AI判断+情报 | Chronos-2+DeepSeek |
| 🏭 商品预测 | 6品种+排名 | Chronos-2 |
| 🏦 A股预测 | 任意输入+Top50 | Kronos-sm |
| 📡 情报 | RSS精选 | — |

### 商品品种
现货黄金/白银(WTI)、国际原油、COMEX铜、LME铝、豆粕(CBOT)
- 数据：10年日线缓存 + 增量，Yahoo 拉取
- 排名：30天预测涨幅排序
- 纵轴标实际单位(USD/盎司、USD/桶等)

### A股功能
- 🏆 Top 50 榜单：左1-25，右26-50，红色渐变
- 5528 条名→码映射，代码或名称输入
- 实时预测+东方财富公告+DeepSeek
- 双数据源：Yahoo→新浪备用

### 技术特性
- SSH 推送，自动构建
- Gradio 登录保护
- yf_dl 兼容 Yahoo v2 多层列
- 商品 CSV 10年缓存

## 核心教训
1. 先验证数据源 → 设计 → 代码
2. 查 API 文档再调参
3. SSH/Git 优先，不手动上传
4. 用官方 requirements.txt
5. 推送前校验
6. 断点+artifact兜底，push冲突靠pull--rebase
