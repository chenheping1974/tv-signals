#!/usr/bin/env python3
"""大宗商品Chronos-2预测排名 → commodity_ranking.json → GitHub"""
import json, time
from datetime import datetime
from pathlib import Path

import pandas as pd
import torch

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OHLCV_FILE = DATA_DIR / "commodities_ohlcv.csv.gz"
RANKING_FILE = DATA_DIR / "commodity_ranking.json"

COMMODITIES = {
    "GC=F": "现货黄金",
    "SI=F": "现货白银",
    "CL=F": "国际原油",
    "HG=F": "COMEX铜",
    "AH=F": "LME铝",
    "ZM=F": "豆粕",
}

HORIZONS = {"7d": 5, "14d": 10, "30d": 22}
PRED_STEPS = 30


def load_pipeline():
    from chronos import Chronos2Pipeline
    print("⏳ 加载 Chronos-2 (~500MB)...")
    pipeline = Chronos2Pipeline.from_pretrained(
        "amazon/chronos-2", device_map="cpu", torch_dtype=torch.float32,
    )
    print("✅ Chronos-2 就绪")
    return pipeline


def predict_all(pipeline):
    df = pd.read_csv(OHLCV_FILE)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])

    results = []
    for sym, name in COMMODITIES.items():
        t0 = time.time()
        print(f"   {sym} ({name})...", end=" ", flush=True)

        sub = df[df["symbol"] == sym].copy()
        if sub.empty or len(sub) < 50:
            print(f"❌ 数据不足 ({len(sub)}行)")
            continue

        prices = sub[["date", "close"]].dropna().copy()
        prices = prices.rename(columns={"date": "timestamp", "close": "target"})
        prices["item_id"] = sym
        prices["timestamp"] = pd.to_datetime(prices["timestamp"], utc=True).dt.tz_localize(None)

        try:
            forecast = pipeline.predict_df(
                prices, prediction_length=PRED_STEPS,
                quantile_levels=[0.1, 0.5, 0.9], freq="B",
            )
        except Exception as e:
            print(f"❌ 预测失败: {e}")
            continue

        fc = forecast.iloc[:PRED_STEPS]
        cols = list(fc.columns)
        median_col = next((c for c in cols if "0.5" in str(c) or "median" in str(c).lower()), cols[1])
        low_col = next((c for c in cols if "0.1" in str(c)), None)
        high_col = next((c for c in cols if "0.9" in str(c)), None)

        current = prices["target"].iloc[-1]
        entry = {"symbol": sym, "name": name, "current": round(float(current), 2)}

        for label, step in HORIZONS.items():
            idx = min(step - 1, len(fc) - 1)
            tgt = float(fc[median_col].iloc[idx])
            pct = (tgt - current) / current * 100
            entry[f"pred_{label}"] = {
                "target": round(tgt, 2), "pct": round(pct, 2),
            }
            if low_col and high_col:
                entry[f"pred_{label}"]["low"] = round(float(fc[low_col].iloc[idx]), 2)
                entry[f"pred_{label}"]["high"] = round(float(fc[high_col].iloc[idx]), 2)

        print(f"当前{current:.2f} 7d:{entry['pred_7d']['pct']:+.1f}% 14d:{entry['pred_14d']['pct']:+.1f}% 30d:{entry['pred_30d']['pct']:+.1f}% ({time.time()-t0:.0f}s)")
        results.append(entry)

    return results


def build_ranking(results):
    rankings = {}
    for label in HORIZONS:
        key = f"pred_{label}"
        sorted_r = sorted(
            [r for r in results if key in r],
            key=lambda x: x[key]["pct"], reverse=True,
        )
        rankings[label] = [
            {"symbol": r["symbol"], "name": r["name"],
             "current": r["current"], **r[key]} for r in sorted_r
        ]
    return rankings


def push_to_supabase(results):
    """写入Supabase，每行 = 一个品种/周期"""
    import os
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("⚠️ 未配置SUPABASE, 跳过")
        return

    supabase = create_client(url, key)
    now = datetime.now().isoformat()
    rows = []
    for r in results:
        for label in HORIZONS:
            pred = r.get(f"pred_{label}", {})
            rows.append({
                "updated": now,
                "horizon": label,
                "symbol": r["symbol"],
                "name": r["name"],
                "current": r["current"],
                "target": pred.get("target"),
                "pct": pred.get("pct"),
                "low": pred.get("low"),
                "high": pred.get("high"),
            })

    supabase.table("commodity_rankings").insert(rows).execute()
    print(f"✅ Supabase: {len(rows)}行")

def main():
    t0 = time.time()
    print(f"🤖 商品排名预测 {datetime.now():%Y-%m-%d %H:%M:%S}")

    df = pd.read_csv(OHLCV_FILE)
    df["date"] = pd.to_datetime(df["date"])
    print(f"📊 数据截止: {df['date'].max().date()}")

    pipeline = load_pipeline()
    results = predict_all(pipeline)
    rankings = build_ranking(results)

    output = {
        "updated": datetime.now().isoformat(),
        "data_date": str(df["date"].max().date()),
        "rankings": rankings,
        "details": results,
    }

    RANKING_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    # 写入Supabase
    push_to_supabase(results)

    elapsed = (time.time() - t0) / 60
    print(f"✅ 完成: {len(results)}品种, {elapsed:.1f}分钟")
    for label in ["7d", "14d", "30d"]:
        top = rankings[label][:3]
        print(f"   {label} Top3: " + " | ".join(f"{r['name']} {r['pct']:+.1f}%" for r in top))


if __name__ == "__main__":
    main()
