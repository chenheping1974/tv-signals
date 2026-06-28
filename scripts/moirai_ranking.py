#!/usr/bin/env python3
"""大宗商品 Moirai-2 预测排名 → moirai_ranking.json"""
import json, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parent.parent
OHLCV_FILE = ROOT / "data/commodities_ohlcv.csv.gz"
RANKING_FILE = ROOT / "data/moirai_ranking.json"

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


def load_model():
    from uni2ts.model.moirai import Moirai2Forecast, Moirai2Module
    print("⏳ 加载 Moirai-2 Small (~100MB)...")
    module = Moirai2Module.from_pretrained("Salesforce/moirai-2.0-R-small")
    model = Moirai2Forecast(
        module=module,
        prediction_length=PRED_STEPS,
        context_length=512,
        target_dim=1,
        feat_dynamic_real_dim=0,
        past_feat_dynamic_real_dim=0,
    )
    print("✅ Moirai-2 就绪")
    return model


def main():
    t0 = time.time()
    print(f"🤖 Moirai-2 商品排名 {datetime.now():%Y-%m-%d %H:%M:%S}")

    if not OHLCV_FILE.exists():
        print("❌ commodities_ohlcv.csv.gz 不存在")
        return

    df = pd.read_csv(OHLCV_FILE)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    print(f"📊 数据截止: {df['date'].max().date()}")

    model = load_model()
    results = []

    for sym, name in COMMODITIES.items():
        bt = time.time()
        print(f"   {sym} ({name})...", end=" ", flush=True)

        sub = df[df["symbol"] == sym]
        if sub.empty or len(sub) < 50:
            print(f"❌ 数据不足")
            continue

        close = sub["close"].tail(512).values.astype(np.float32)
        current = float(close[-1])

        try:
            # Moirai-2 输入: (batch=1, time, dim=1)
            past = torch.tensor(close).view(1, -1, 1)
            forecast = model(past_target=past)
            # forecast: (1, PRED_STEPS, num_samples)
            if isinstance(forecast, torch.Tensor):
                samples = forecast[0]  # (PRED_STEPS, num_samples)
                median = samples.median(dim=-1).values.numpy()
                low = samples.kthvalue(max(1, samples.size(-1) // 10), dim=-1).values.numpy()
                high = samples.kthvalue(max(1, samples.size(-1) * 9 // 10), dim=-1).values.numpy()
            else:
                median = forecast[0].numpy().flatten()
                low = high = median
        except Exception as e:
            print(f"❌ {e}")
            continue

        entry = {"symbol": sym, "name": name, "current": round(current, 2)}
        for label, step in HORIZONS.items():
            idx = min(step - 1, len(median) - 1)
            tgt = float(median[idx])
            pct = (tgt - current) / current * 100
            entry[f"pred_{label}"] = {"target": round(tgt, 2), "pct": round(pct, 2)}
            try:
                entry[f"pred_{label}"]["low"] = round(float(low[idx]), 2)
                entry[f"pred_{label}"]["high"] = round(float(high[idx]), 2)
            except:
                pass

        print(f"当前{current:.2f} 7d:{entry['pred_7d']['pct']:+.1f}% 14d:{entry['pred_14d']['pct']:+.1f}% 30d:{entry['pred_30d']['pct']:+.1f}% ({time.time()-bt:.0f}s)")
        results.append(entry)

    # 排名
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
        "rankings": {h: [
            {"symbol": r["symbol"], "name": r["name"],
             "current": r["current"], **r[f"pred_{h}"]}
            for r in rankings[h]
        ] for h in HORIZONS},
        "details": results,
    }

    RANKING_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    elapsed = (time.time() - t0) / 60
    print(f"✅ 完成: {len(results)}品种, {elapsed:.1f}分钟")
    for label in ["7d", "14d", "30d"]:
        top = rankings[label][:3]
        print(f"   {label} Top3: " + " | ".join(
            f"{r['name']} {r['pct']:+.1f}%" for r in top))


if __name__ == "__main__":
    main()
