#!/usr/bin/env python3
"""
A股横截面选股 — Kronos-small 批量预测 30 天涨跌幅 → ranking.json
OHLCV 数据增量更新：首次下载全量，每天追加当日数据
"""

import json, time, sys, os, io
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OHLCV_FILE = DATA_DIR / "ohlcv.csv.gz"
RANKING_FILE = DATA_DIR / "ranking.json"
PROGRESS_FILE = DATA_DIR / "ranking_progress.json"
STOCK_POOL_FILE = DATA_DIR / "stock_pool.json"

PRED_DAYS = 30
MAX_STOCKS = 5000
BATCH_DL = 5    # 小批量避免超时
BATCH_PRED = 20  # 每 N 只存一次断点

# ── 股票池 ──────────────────────────────────────────
def load_pool():
    """加载预生成股票池（akshare 验证的有效股票）"""
    pool = json.loads(STOCK_POOL_FILE.read_text())
    valid = [s for s in pool if not s["code"].startswith(("688", "8"))]
    return valid[:MAX_STOCKS]


def to_sina(code):
    """新浪财经API格式: sh600519 / sz000858"""
    return f"sh{code}" if code.startswith("6") else f"sz{code}"


def download_sina(code):
    """从新浪财经下载日线OHLCV"""
    import requests, json
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={to_sina(code)}&scale=240&ma=no&datalen=400"
    try:
        r = requests.get(url, timeout=15)
        data = json.loads(r.text)
        if not isinstance(data, list) or len(data) < 60:
            return None
        df = pd.DataFrame(data)
        df = df.rename(columns={"day": "date", "open": "open", "high": "high", "low": "low", "close": "close"})
        df["date"] = pd.to_datetime(df["date"], format='mixed')
        df["code"] = code
        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=["open", "high", "low", "close"])[["date", "code", "open", "high", "low", "close"]]
    except:
        return None


# ── OHLCV 增量更新 ─────────────────────────────────
def update_ohlcv(pool):
    """增量更新 OHLCV：读取已有数据，仅追加当日最新"""
    existing = pd.read_csv(OHLCV_FILE) if OHLCV_FILE.exists() else pd.DataFrame()
    if not existing.empty:
        existing["date"] = pd.to_datetime(existing["date"], format='mixed')
        last_date = existing["date"].max()
        today = pd.Timestamp.now().normalize()
        if last_date >= today - pd.Timedelta(days=1):
            print(f"✅ OHLCV 已最新 (截止 {last_date.date()})")
            return existing
        print(f"📥 追加 {last_date.date()} → {today.date()} 数据...")

    new_rows, codes = [], set(existing["code"].astype(str).str.zfill(6).unique()) if not existing.empty else set()
    for i, s in enumerate(pool):
        code = str(s["code"]).zfill(6)
        if code in codes:
            # 已有历史：增量追加
            df = download_sina(code)
            if df is not None and not existing.empty:
                existing_dates = set(existing[existing["code"].astype(str).str.zfill(6) == code]["date"])
                df = df[~df["date"].isin(existing_dates)]
            if df is not None and len(df) > 0:
                new_rows.append(df)
        else:
            # 新股票：首次下载全量
            df = download_sina(code)
            if df is not None and len(df) >= 60:
                new_rows.append(df)
                codes.add(code)
                print(f"   🆕 新纳入 {code}")
        if i % 200 == 0:
            print(f"   [{i+1}/{len(pool)}] {len(new_rows)} 批新数据")
        time.sleep(0.05)

    if not new_rows:
        return existing

    new_df = pd.concat(new_rows, ignore_index=True)
    combined = pd.concat([existing, new_df], ignore_index=True) if not existing.empty else new_df
    combined = combined.drop_duplicates(subset=["date", "code"]).sort_values(["code", "date"])
    combined.to_csv(OHLCV_FILE, index=False, compression="gzip")
    print(f"✅ OHLCV: {combined['code'].nunique()}只, {len(combined)}行, +{len(new_df)}行")
    return combined

    if not new_rows:
        print("⚠️ 无新数据")
        return existing

    new_df = pd.concat(new_rows, ignore_index=True)
    new_df["date"] = pd.to_datetime(new_df["date"], format='mixed').dt.normalize()

    if not existing.empty:
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "code"]).sort_values(["code", "date"])
    else:
        combined = new_df.sort_values(["code", "date"])

    combined.to_parquet(OHLCV_FILE, index=False)
    print(f"✅ OHLCV: {combined['code'].nunique()} 只, {len(combined)} 行, 截止 {combined['date'].max().date()}")
    return combined


# ── Kronos 预测 ─────────────────────────────────────
def load_kronos():
    kronos_path = Path("/tmp/kronos_repo")
    if not (kronos_path / "model.py").exists():
        os.system(f"rm -rf {kronos_path} && git clone --depth 1 https://github.com/shiyu-coder/Kronos {kronos_path} -q")
    sys.path.insert(0, str(kronos_path))
    from model import Kronos, KronosTokenizer, KronosPredictor
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    return KronosPredictor(model, tokenizer, device="cpu", max_context=512)


def predict_single(predictor, ohlcv, code):
    """预测单只股票 30 天涨跌幅"""
    df = ohlcv[ohlcv["code"].astype(str).str.zfill(6) == str(code).zfill(6)].sort_values("date").tail(512)
    if len(df) < 60:
        return None
    try:
        last_date = pd.to_datetime(df["date"], format='mixed').iloc[-1]
        y_ts = pd.Series(pd.date_range(start=last_date + pd.Timedelta(days=1), periods=PRED_DAYS, freq="B"))
        result = predictor.predict(
            df=df[["open", "high", "low", "close"]],
            x_timestamp=pd.to_datetime(df["date"], format='mixed'),
            y_timestamp=y_ts,
            pred_len=PRED_DAYS, T=1.0, top_p=0.9, sample_count=1,
        )
        if result is None or len(result) == 0:
            return None
        last_close = df["close"].iloc[-1]
        pred_col = "close" if "close" in result.columns else result.columns[0]
        pred_close = result[pred_col].iloc[-1]
        pct = (pred_close - last_close) / last_close * 100
        return {"code": code, "last_close": round(float(last_close), 2),
                "pred_close": round(float(pred_close), 2), "pct_change": round(float(pct), 2)}
    except Exception as e:
        print(f"   ⚠️ {code} 预测失败: {e}")
        return None


# ── 主函数 ──────────────────────────────────────────
def main():
    t0 = time.time()
    print(f"🚀 A股横截面选股 {datetime.now():%Y-%m-%d %H:%M:%S}")

    # 1. 加载股票池
    pool = load_pool()
    print(f"📊 股票池: {len(pool)} 只")

    # 2. OHLCV 增量更新
    ohlcv = update_ohlcv(pool)

    # 3. 加载 Kronos
    print("🤖 加载 Kronos-small...")
    predictor = load_kronos()

    # 4. 断点续跑
    if PROGRESS_FILE.exists():
        prog = json.loads(PROGRESS_FILE.read_text())
        results = prog.get("results", [])
        start_idx = prog.get("next_idx", 0)
        print(f"📎 断点续跑: {len(results)} 只, 从 {start_idx} 继续")
    else:
        results, start_idx = [], 0

    # 5. 逐只预测
    total = len(pool)
    print(f"🔮 预测 {total} 只 ({total - start_idx} 剩余)...")
    for i in range(start_idx, total):
        s = pool[i]
        code = s["code"]
        print(f"   [{i+1}/{total}] {code}", end=" ", flush=True)
        r = predict_single(predictor, ohlcv, code)
        if r:
            r["name"] = s.get("name", "")
            results.append(r)
            print(f"{'🟢' if r['pct_change'] > 0 else '🔴'} {r['pct_change']:+.2f}%")
        else:
            print("⏭️")

        if (i + 1) % BATCH_PRED == 0:
            prog = {"results": results, "next_idx": i + 1, "total": total,
                    "updated": datetime.now().isoformat()}
            PROGRESS_FILE.write_text(json.dumps(prog, ensure_ascii=False, indent=2))
            elapsed = (time.time() - t0) / 60
            print(f"   💾 [{i+1}/{total}] {len(results)} 条, {elapsed:.0f}min")

    # 6. 排序保存
    results.sort(key=lambda x: x["pct_change"], reverse=True)
    output = {"updated": datetime.now().isoformat(), "total": len(results), "ranking": results}
    RANKING_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    elapsed = (time.time() - t0) / 60
    print(f"✅ {len(results)} 只排序完成, {elapsed:.0f} 分钟")
    for r in results[:5]:
        print(f"   {r['code']} {r.get('name','')}: {r['pct_change']:+.2f}%")

if __name__ == "__main__":
    main()
