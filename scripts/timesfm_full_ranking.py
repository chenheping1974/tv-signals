#!/usr/bin/env python3
"""TimesFM 2.5 全量A股预测 → timesfm_full_ranking.json"""
import json, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OHLCV_FILE = ROOT / "data/ohlcv_full.csv.gz"
RANKING_FILE = ROOT / "data/timesfm_full_ranking.json"
NAME_MAP_FILE = ROOT / "data/name_map.json"

HORIZONS = {"30d": 22, "60d": 44, "128d": 128}
PRED_STEPS = 128
BATCH_SIZE = 200


def load_model():
    from transformers import TimesFm2_5ModelForPrediction, TimesFm2_5Config
    print("⏳ 加载 TimesFM 2.5 (transformers, horizon=30)...")
    config = TimesFm2_5Config(horizon_length=PRED_STEPS)
    model = TimesFm2_5ModelForPrediction.from_pretrained(
        "google/timesfm-2.5-200m-transformers", config=config, device_map="auto",
    )
    print("✅ TimesFM 2.5 就绪")
    return model


def main():
    t0 = time.time()
    print(f"🤖 TimesFM全量排名 {datetime.now():%Y-%m-%d %H:%M:%S}")

    nm = json.loads(NAME_MAP_FILE.read_text())
    name_of = {k: v for k, v in nm.items() if k.isdigit() and len(k) == 6}

    df = pd.read_csv(OHLCV_FILE)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"])
    print(f"📊 OHLCV: {df['code'].nunique()}只, 截止{df['date'].max().date()}")

    model = load_model()

    series, codes = [], []
    for code, grp in df.groupby("code"):
        code_str = str(code).zfill(6)
        close = grp["close"].tail(512).values.astype(np.float32)
        if len(close) < 60:
            continue
        series.append(close)
        codes.append(code_str)

    print(f"📊 有效: {len(series)}只")

    results = []
    for b in range(0, len(series), BATCH_SIZE):
        be = min(b + BATCH_SIZE, len(series))
        print(f"   [{b+1}-{be}/{len(series)}] ...", end=" ", flush=True)
        bt = time.time()
        try:
            import torch
            model_device = model.device
            inputs = [torch.tensor(s, dtype=torch.float32, device=model_device) for s in series[b:be]]
            with torch.no_grad():
                outputs = model(past_values=inputs, return_dict=True)
            point = outputs.mean_predictions.cpu().numpy()
            qfull = outputs.full_predictions.cpu().numpy()
        except Exception as e:
            print(f"❌ {e}")
            continue

        for i in range(len(series[b:be])):
            current = float(series[b+i][-1])
            pred = point[i, :PRED_STEPS]
            q = qfull[i, :PRED_STEPS]
            entry = {
                "symbol": codes[b+i],
                "name": name_of.get(codes[b+i], codes[b+i]),
                "current": round(current, 2),
            }
            for label, step in HORIZONS.items():
                idx = min(step - 1, PRED_STEPS - 1)
                tgt = float(pred[idx])
                pct = (tgt - current) / current * 100
                entry[f"pred_{label}"] = {"target": round(tgt, 2), "pct": round(pct, 2)}
                entry[f"pred_{label}"]["low"] = round(float(q[idx, 0]), 2)
                entry[f"pred_{label}"]["high"] = round(float(q[idx, 8]), 2)
            results.append(entry)

        print(f"{time.time()-bt:.0f}s")

    rankings = {}
    for label in HORIZONS:
        key = f"pred_{label}"
        rankings[label] = sorted(
            [r for r in results if key in r],
            key=lambda x: x[key]["pct"], reverse=True,
        )

    output = {
        "updated": datetime.now().isoformat(),
        "data_date": str(df["date"].max().date()),
        "total_stocks": len(results),
        "rankings": {h: [
            {"symbol": r["symbol"], "name": r["name"],
             "current": r["current"], **r[f"pred_{h}"]}
            for r in rankings[h][:50]
        ] for h in HORIZONS},
        "details": results,
    }

    RANKING_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    elapsed = (time.time() - t0) / 60
    print(f"✅ 完成: {len(results)}只, {elapsed:.1f}分钟")
    for label in ["7d", "14d", "30d"]:
        top = rankings[label][:3]
        print(f"   {label} Top3: " + " | ".join(
            f"{r['name']} {r['pct']:+.1f}%" for r in top))


if __name__ == "__main__":
    main()
