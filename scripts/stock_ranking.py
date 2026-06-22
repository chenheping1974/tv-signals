#!/usr/bin/env python3
"""A股横截面选股 — Kronos-small 批量预测30天涨跌幅 → ranking.json"""

import json, time, sys, os, re
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf

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

# ── OHLCV 增量（yfinance批量） ──────────────────────
def update_ohlcv(pool):
    existing = pd.read_csv(OHLCV_FILE) if OHLCV_FILE.exists() else pd.DataFrame()
    if not existing.empty:
        existing["date"] = pd.to_datetime(existing["date"], format='ISO8601')
        last_date = existing["date"].max()
        today = pd.Timestamp.now().normalize()
        if last_date >= today - pd.Timedelta(days=1):
            print(f"✅ OHLCV已最新 (截止{last_date.date()})")
            return existing, False

    # yfinance批量抽查：只取前10只查有无新数据
    need_update = False
    if not existing.empty:
        tickers = []
        for s in pool[:10]:
            code = str(s["code"]).zfill(6)
            tickers.append(f"{code}.{'SS' if code.startswith('6') else 'SZ'}")
        try:
            data = yf.download(tickers, period="5d", progress=False)
            if isinstance(data, tuple): data = data[0]
            for s, t in zip(pool[:10], tickers):
                if t in data.columns:
                    new_last = data[t].dropna().index.max()
                    code_str = str(s["code"]).zfill(6)
                    mask = existing["code"].astype(str).str.zfill(6) == code_str
                    if mask.any() and new_last > existing[mask]["date"].max():
                        need_update = True
                        break
        except: pass

    if not need_update:
        print("✅ 无需更新（今日无新数据）")
        return existing, False

    # 批量增量：10只一组
    print(f"📥 yfinance批量增量({len(pool)}只)...")
    new_rows, codes = [], set(existing["code"].astype(str).str.zfill(6).unique())
    for i in range(0, len(pool), 10):
        batch = pool[i:i+10]
        tickers = []
        for s in batch:
            code = str(s["code"]).zfill(6)
            tickers.append(f"{code}.{'SS' if code.startswith('6') else 'SZ'}")
        try:
            data = yf.download(tickers, period="5d", progress=False)
            if isinstance(data, tuple): data = data[0]
            for s, t in zip(batch, tickers):
                if t not in data.columns: continue
                df = data[t].dropna()
                if df.empty: continue
                df = df.reset_index()
                df.columns = [c.lower() for c in df.columns]
                df = df.rename(columns={"date":"date"})
                code = str(s["code"]).zfill(6)
                if code in codes:
                    mask = existing["code"].astype(str).str.zfill(6) == code
                    if mask.any():
                        old_dates = set(existing[mask]["date"])
                        df = df[~df["date"].isin(old_dates)]
                if len(df) > 0:
                    df["code"] = code
                    for c in ["open","high","low","close"]:
                        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
                    new_rows.append(df[["date","code","open","high","low","close"]].dropna())
        except: pass
        if i % 200 == 0:
            print(f"   [{min(i+10,len(pool))}/{len(pool)}] {len(new_rows)}批")
        time.sleep(0.5)

    if not new_rows:
        return existing, True
    new_df = pd.concat(new_rows, ignore_index=True)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date","code"]).sort_values(["code","date"])
    combined.to_csv(OHLCV_FILE, index=False, compression="gzip")
    print(f"✅ OHLCV: {combined['code'].nunique()}只, +{len(new_df)}行")
    return combined, True

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

    ohlcv, has_new = update_ohlcv(pool)
    if not has_new and RANKING_FILE.exists():
        print("✅ 无新数据,跳过预测")
        return

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
