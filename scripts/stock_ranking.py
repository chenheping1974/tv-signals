#!/usr/bin/env python3
"""
A股横截面选股 — 粗筛1000只 + Kronos-small预测30天涨跌幅 → ranking.json
每天16:30由GitHub Actions触发，结果存到data/ranking.json
"""

import os, sys, json, time, warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import requests

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── 配置 ────────────────────────────────────────────
OUTPUT_FILE = DATA_DIR / "ranking.json"
PROGRESS_FILE = DATA_DIR / "ranking_progress.json"  # 断点续跑
BATCH_SIZE = 10    # 每10只存一次进度
MAX_STOCKS = 1000  # 目标粗筛数量
PRED_DAYS = 30     # 预测未来天数

# ── 粗筛函数 ────────────────────────────────────────
def fetch_all_stocks():
    """akshare拉全市场股票，粗筛到~1000只"""
    print("📊 拉取全市场股票数据...")
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        print(f"❌ akshare 拉取失败: {e}")
        return pd.DataFrame()

    print(f"   全市场: {len(df)} 只")
    df["代码"] = df["代码"].astype(str)

    # 硬过滤
    df = df[~df["名称"].str.contains("ST|退", na=False)]  # ST/退市
    df = df[~df["代码"].str.startswith("688")]             # 科创板
    df = df[~df["代码"].str.match(r"^8\d{5}")]            # 北交所
    print(f"   排除科创板/北交所/ST: {len(df)} 只")

    # 流动性: 日均成交额 > 1亿
    if "成交额" in df.columns:
        df["成交额"] = pd.to_numeric(df["成交额"], errors="coerce")
        df = df[df["成交额"] > 100_000_000]  # 1亿
        print(f"   成交额 > 1亿: {len(df)} 只")

    # PE过滤: 0 < PE < 200
    if "市盈率-动态" in df.columns:
        pe_col = "市盈率-动态"
    elif "市盈率" in df.columns:
        pe_col = "市盈率"
    else:
        pe_col = None
    if pe_col:
        df[pe_col] = pd.to_numeric(df[pe_col], errors="coerce")
        df = df[(df[pe_col] > 0) & (df[pe_col] < 200)]
        print(f"   PE 0-200: {len(df)} 只")

    # 市值（如果有数据）
    if "总市值" in df.columns:
        df["总市值"] = pd.to_numeric(df["总市值"], errors="coerce")
        df = df[df["总市值"] > 8_000_000_000]  # 80亿
        print(f"   市值 > 80亿: {len(df)} 只")

    # 取前MAX_STOCKS只（按成交额排序）
    if "成交额" in df.columns:
        df = df.sort_values("成交额", ascending=False)
    df = df.head(MAX_STOCKS)

    print(f"✅ 最终粗筛: {len(df)} 只")
    return df[["代码", "名称"]].reset_index(drop=True)


# ── Kronos 预测 ─────────────────────────────────────
def load_kronos():
    """懒加载 Kronos 模型"""
    import importlib.util
    if importlib.util.find_spec("model") is None:
        # 如果没有安装kronos包，直接从HF克隆
        kronos_path = Path("/tmp/kronos_repo")
        if not (kronos_path / "model.py").exists():
            print("📦 克隆 Kronos 仓库...")
            os.system(f"rm -rf {kronos_path} && git clone --depth 1 https://github.com/shiyu-coder/Kronos {kronos_path} 2>&1 | tail -1")
        sys.path.insert(0, str(kronos_path))

    from model import Kronos, KronosTokenizer, KronosPredictor

    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
    return predictor


def fetch_stock_ohlcv(code):
    """拉单只股票1年日线OHLCV"""
    suffix = "SH" if code.startswith(("6", "5")) else "SZ"
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                                end_date=datetime.now().strftime("%Y%m%d"),
                                adjust="qfq")
        if df is None or len(df) < 100:
            return None
        df = df.rename(columns={"日期": "date", "开盘": "open", "最高": "high",
                                 "最低": "low", "收盘": "close", "成交量": "volume"})
        # 确保有OHLC列
        for col in ["open", "high", "low", "close"]:
            if col not in df.columns:
                return None
        return df[["date", "open", "high", "low", "close"]].dropna()
    except Exception as e:
        print(f"   ⚠️ {code} 数据拉取失败: {e}")
        return None


def predict_single(predictor, code, name):
    """预测单只股票30天涨跌幅"""
    df = fetch_stock_ohlcv(code)
    if df is None or len(df) < 100:
        return None

    try:
        result = predictor.predict(
            df=df[["open", "high", "low", "close"]],
            x_timestamp=df["date"].tolist(),
            y_timestamp=None,
            pred_len=PRED_DAYS,
            T=1.0,
            top_p=0.9,
            sample_count=1,
        )
        if result is None or len(result) == 0:
            return None
        last_close = df["close"].iloc[-1]
        pred_close = result["close"].iloc[-1] if "close" in result.columns else result.iloc[-1, 0]
        pct_change = (pred_close - last_close) / last_close * 100
        return {
            "code": code,
            "name": name,
            "last_close": round(float(last_close), 2),
            "pred_close": round(float(pred_close), 2),
            "pct_change": round(float(pct_change), 2),
        }
    except Exception as e:
        print(f"   ⚠️ {code} {name} 预测失败: {e}")
        return None


# ── 主函数 ──────────────────────────────────────────
def main():
    print(f"🚀 A股横截面选股开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    t0 = time.time()

    # 1. 粗筛
    stocks = fetch_all_stocks()
    if stocks.empty:
        print("❌ 粗筛结果为空")
        return

    # 2. 加载断点
    if PROGRESS_FILE.exists():
        progress = json.loads(PROGRESS_FILE.read_text())
        results = progress.get("results", [])
        start_idx = progress.get("next_idx", 0)
        print(f"📎 断点续跑: 已处理 {len(results)} 只，从第 {start_idx} 只继续")
    else:
        results = []
        start_idx = 0

    # 3. 加载 Kronos
    print("🤖 加载 Kronos-small 模型...")
    predictor = load_kronos()

    # 4. 逐只预测
    total = len(stocks)
    print(f"🔮 开始预测 {total} 只股票（剩余 {total - start_idx} 只）...")
    for i in range(start_idx, total):
        row = stocks.iloc[i]
        code, name = row["代码"], row["名称"]
        print(f"   [{i+1}/{total}] {code} {name}...", end=" ", flush=True)

        result = predict_single(predictor, code, name)
        if result:
            results.append(result)
            pct = result["pct_change"]
            emoji = "🟢" if pct > 0 else "🔴"
            print(f"{emoji} {pct:+.2f}%")
        else:
            print("⏭️ 跳过")

        # 每BATCH_SIZE只保存断点
        if (i + 1) % BATCH_SIZE == 0:
            progress = {"results": results, "next_idx": i + 1, "total": total,
                        "updated": datetime.now().isoformat()}
            PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2))
            elapsed = time.time() - t0
            rate = (i + 1 - start_idx) / elapsed * 60 if elapsed > 0 else 0
            print(f"   💾 已存断点 [{i+1}/{total}] 速度: {rate:.1f} 只/分钟")

    # 5. 排序保存
    results.sort(key=lambda x: x["pct_change"], reverse=True)
    output = {
        "updated": datetime.now().isoformat(),
        "total_stocks": len(results),
        "ranking": results,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    # 清理断点
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    elapsed = (time.time() - t0) / 60
    print(f"\n✅ 完成! {len(results)} 只排序完成，耗时 {elapsed:.0f} 分钟")
    top = results[:5]
    for r in top:
        print(f"   {r['code']} {r['name']}: {r['pct_change']:+.2f}%")

if __name__ == "__main__":
    main()
