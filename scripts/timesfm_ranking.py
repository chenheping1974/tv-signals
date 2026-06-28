#!/usr/bin/env python3
"""A股 TimesFM 2.5 预测排名 → timesfm_ranking.json"""
import json, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OHLCV_FILE = ROOT / "data/ohlcv.csv.gz"
POOL_FILE = ROOT / "data/stock_pool.json"
RANKING_FILE = ROOT / "data/timesfm_ranking.json"

HORIZONS = {"7d": 5, "14d": 10, "30d": 22}
PRED_STEPS = 30
BATCH_SIZE = 200


def load_model():
    import timesfm as tfm
    print("⏳ 加载 TimesFM 2.5 (~400MB)...")
    model = tfm.TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch"
    )
    model.compile(tfm.ForecastConfig(
        max_context=512, max_horizon=PRED_STEPS,
        normalize_inputs=True, use_continuous_quantile_head=True,
    ))
    print("✅ TimesFM 2.5 就绪")
    return model


def main():
    t0 = time.time()
    print(f"🤖 TimesFM A股排名 {datetime.now():%Y-%m-%d %H:%M:%S}")

    pool = json.loads(POOL_FILE.read_text())
    stocks = pool if isinstance(pool, list) else pool.get("stocks", pool)
    pool_codes = {str(s["code"]).zfill(6): s["name"] for s in stocks}

    df = pd.read_csv(OHLCV_FILE)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"])
    print(f"📊 OHLCV: {df['code'].nunique()}只, 截止{df['date'].max().date()}")

    model = load_model()

    series, codes = [], []
    for code, grp in df.groupby("code"):
        code_str = str(code).zfill(6)
        if code_str not in pool_codes:
            continue
        close = grp["close"].tail(512).values.astype(np.float32)
        if len(close) < 60:
            continue
        series.append(close)
        codes.append(code_str)

    print(f"📊 有效: {len(series)}只")

    all_results = []
    for b in range(0, len(series), BATCH_SIZE):
        be = min(b + BATCH_SIZE, len(series))
        print(f"   [{b+1}-{be}/{len(series)}] ...", end=" ", flush=True)
        bt = time.time()
        try:
            point, quantile = model.forecast(horizon=PRED_STEPS, inputs=series[b:be])
        except Exception as e:
            print(f"❌ {e}")
            continue

        for i in range(len(series[b:be])):
            current = float(series[b+i][-1])
            pred = point[i]
            q = quantile[i] if quantile is not None else None
            entry = {
                "symbol": codes[b+i],
                "name": pool_codes.get(codes[b+i], codes[b+i]),
                "current": round(current, 2),
            }
            for label, step in HORIZONS.items():
                idx = min(step - 1, PRED_STEPS - 1)
                tgt = float(pred[idx])
                pct = (tgt - current) / current * 100
                entry[f"pred_{label}"] = {"target": round(tgt, 2), "pct": round(pct, 2)}
                if q is not None:
                    entry[f"pred_{label}"]["low"] = round(float(q[idx, 1]), 2)
                    entry[f"pred_{label}"]["high"] = round(float(q[idx, 8]), 2)
            all_results.append(entry)

        print(f"{time.time()-bt:.0f}s")

    rankings = {}
    for label in HORIZONS:
        key = f"pred_{label}"
        rankings[label] = sorted(
            [r for r in all_results if key in r],
            key=lambda x: x[key]["pct"], reverse=True,
        )

    output = {
        "updated": datetime.now().isoformat(),
        "data_date": str(df["date"].max().date()),
        "rankings": {h: [
            {"symbol": r["symbol"], "name": r["name"],
             "current": r["current"], **r[f"pred_{h}"]}
            for r in rankings[h][:50]
        ] for h in HORIZONS},
        "details": all_results,
    }

    RANKING_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    elapsed = (time.time() - t0) / 60
    print(f"✅ 完成: {len(all_results)}只, {elapsed:.1f}分钟")
    for label in ["7d", "14d", "30d"]:
        top = rankings[label][:3]
        print(f"   {label} Top3: " + " | ".join(
            f"{r['name']} {r[f'pred_{label}']['pct']:+.1f}%" for r in top))


if __name__ == "__main__":
    main()
