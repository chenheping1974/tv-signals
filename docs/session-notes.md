# 项目沟通笔记

## 系统总览

| 系统 | 功能 | 模型 | 触发 | 输出 |
|------|------|------|------|------|
| 📰 情报 | 商品+A股新闻精选 | DeepSeek | 每天 21:00 | Feedly |
| 🏆 选股 | A股横截面排序 | Kronos-small | 每天 16:30 | ranking.json |
| 📈 预测 | 商品+A股实时预测 | Chronos-2 + Kronos-sm | 随时 | HF Space |
| 💰 成本 | $0/月 | | | |

## 情报系统

华尔街见闻 API → GitHub Actions (21:00) → DeepSeek → RSS XML → GitHub Pages → Feedly + Space 情报页

## 选股系统

### 股票池
- 4条件：ST/科创北交/市值>80亿/成交额>1亿 → ~1000只
- 每周一 Mac 本地 `python scripts/screen_pool.py` 重筛
- GitHub Actions (16:30) 增量+预测

### 数据流
```
Mac(每周)：screen_pool.py → 腾讯筛池 → 新浪 OHLCV → git push
Actions(每天)：抽查10只增量 → Kronos → ranking.json → artifact+push
Space(随时)：读 ranking.json → 榜单 | 个股+公告+DeepSeek
```

### 可靠性
- 断点续跑 + artifact 保底（push 失败数据不丢）
- `pull --rebase` 防 git 冲突
- 官方 requirements.txt

## 预测平台 (HF Space)

### 三个标签

| 标签 | 功能 |
|------|------|
| 🏭 商品预测 | Chronos-2 预测 + DeepSeek + 30天排名 |
| 🏦 A股预测 | Kronos-sm 预测 + Top50榜单 + 任意输入 |
| 📡 情报 | 左商品右A股，一键刷新 |

### 商品
- 6品种：现货黄金/白银、WTI原油、COMEX铜、LME铝、豆粕
- 10年日线 CSV 缓存 + 增量
- 纵轴标实际单位
- yf_dl 兼容 Yahoo v2 多层列 + tuple 返回

### A股
- Top50 榜单：左1-25 右26-50，红色渐变
- 5528 名→码映射
- 东方财富公告 + DeepSeek
- Yahoo→新浪双源备用

## 核心教训
1. 先验证数据源 → 设计 → 代码
2. SSH/Git 优先
3. 用官方 requirements.txt
4. artifact 保底防丢数据
5. 全局替换慎用——用前查影响范围
6. push 加 pull--rebase 防冲突
