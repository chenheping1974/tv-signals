#!/usr/bin/env python3
"""A股横截面选股 — Kronos-small 批量预测30天涨跌幅 → ranking.json"""

import json, time, sys, os, re
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import requests as req

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OHLCV_FILE = DATA_DIR / "ohlcv.csv.gz"
RANKING_FILE = DATA_DIR / "ranking.json"
STOCK_POOL_FILE = DATA_DIR / "stock_pool.json"

PRED_DAYS = 30
MAX_STOCKS = 5000

# ── 股票池 ──────────────────────────────────────────
def load_pool():
    raw = json.loads(STOCK_POOL_FILE.read_text())
    if isinstance(raw, dict) and "stocks" in raw:
        return raw["stocks"][:MAX_STOCKS]
    return raw[:MAX_STOCKS]

# ── OHLCV 加载 ─────────────────────────────────────
def load_ohlcv():
    df = pd.read_csv(OHLCV_FILE)
    df["date"] = pd.to_datetime(df["date"], format='ISO8601')
    print(f"📊 OHLCV: {df['code'].nunique()}只, 截止{df['date'].max().date()}")
    return df

# ── Kronos 模型 ─────────────────────────────────────
def load_kronos():
    kronos_path = "/tmp/kronos_repo"
    if not os.path.exists(f"{kronos_path}/model.py"):
        os.system(f"rm -rf {kronos_path} && git clone --depth 1 https://github.com/shiyu-coder/Kronos {kronos_path} -q")
    sys.path.insert(0, kronos_path)
    from model import Kronos, KronosTokenizer, KronosPredictor
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    return KronosPredictor(model, tokenizer, device="cpu", max_context=512)

# ── 预测 ────────────────────────────────────────────
def predict_single(predictor, ohlcv, code):
    df = ohlcv[ohlcv["code"].astype(str).str.zfill(6) == str(code).zfill(6)].sort_values("date").tail(512)
    if len(df) < 60:
        return None
    try:
        last_date = pd.to_datetime(df["date"]).iloc[-1]
        y_ts = pd.Series(pd.date_range(start=last_date + pd.Timedelta(days=1), periods=PRED_DAYS, freq="B"))
        result = predictor.predict(
            df=df[["open","high","low","close"]],
            x_timestamp=pd.to_datetime(df["date"]),
            y_timestamp=y_ts,
            pred_len=PRED_DAYS, T=1.0, top_p=0.9, sample_count=1,
        )
        if result is None or len(result) == 0:
            return None
        last_close = df["close"].iloc[-1]
        pred_col = "close" if "close" in result.columns else result.columns[0]
        pred_close = result[pred_col].iloc[-1]
        pct = (pred_close - last_close) / last_close * 100
        return {"code": code, "last_close": round(float(last_close),2),
                "pred_close": round(float(pred_close),2), "pct_change": round(float(pct),2)}
    except Exception as e:
        print(f"   ⚠️ {code}: {e}")
        return None

# ── 主函数 ──────────────────────────────────────────
def main():
    t0 = time.time()
    print(f"🚀 A股选股 {datetime.now():%Y-%m-%d %H:%M:%S}")

    pool = load_pool()
    print(f"📊 股票池: {len(pool)} 只")

    # 今天已跑过就跳
    if RANKING_FILE.exists():
        old = json.loads(RANKING_FILE.read_text())
        if old.get("updated", "")[:10] == datetime.now().strftime("%Y-%m-%d"):
            print("✅ 今日已更新, 跳过")
            return

    ohlcv = load_ohlcv()
    print("🤖 加载 Kronos-small...")
    predictor = load_kronos()

    results = []
    for i, s in enumerate(pool):
        code = s["code"]
        print(f"   [{i+1}/{len(pool)}] {code}", end=" ", flush=True)
        r = predict_single(predictor, ohlcv, code)
        if r:
            r["name"] = s.get("name", "")
            results.append(r)
            print(f"{'🟢' if r['pct_change']>0 else '🔴'} {r['pct_change']:+.2f}%")
        else:
            print("⏭️")
        if (i+1) % 100 == 0:
            print(f"   [{i+1}/{len(pool)}] {len(results)}条, {((time.time()-t0)/60):.0f}min")

    results.sort(key=lambda x: x["pct_change"], reverse=True)
    RANKING_FILE.write_text(json.dumps({"updated": datetime.now().isoformat(), "total": len(results), "ranking": results}, ensure_ascii=False, indent=2))
    print(f"✅ {len(results)}只, {((time.time()-t0)/60):.0f}分钟")
    for r in results[:5]:
        print(f"   {r['code']} {r.get('name','')}: {r['pct_change']:+.2f}%")

if __name__ == "__main__":
    main()
