#!/usr/bin/env python3
"""大宗商品 Moirai-2 预测排名 → moirai_ranking.json"""
import json, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

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
CTX_LEN = 512  # 数据窗口, 模型会取1680内但用不了那么多


def load_predictor():
    """官方API: create_predictor"""
    from uni2ts.model.moirai2 import Moirai2Forecast, Moirai2Module

    print("⏳ 加载 Moirai-2 Small...")
    module = Moirai2Module.from_pretrained("Salesforce/moirai-2.0-R-small")
    model = Moirai2Forecast(
        module=module,
        prediction_length=PRED_STEPS,
        context_length=1680,
        target_dim=1,
        feat_dynamic_real_dim=0,
        past_feat_dynamic_real_dim=0,
    )
    predictor = model.create_predictor(batch_size=1)
    print("✅ Moirai-2 就绪")
    return predictor


def gluonts_dataset(close_prices):
    """构造单变量GluonTS数据集"""
    from gluonts.dataset.common import ListDataset
    # GluonTS期望: [{"target": array, "start": timestamp}, ...]
    entry = {
        "target": close_prices,
        "start": pd.Timestamp("2016-01-01"),
        "freq": "B",
    }
    return ListDataset([entry], freq="B")


def main():
    t0 = time.time()
    print(f"🤖 Moirai-2 商品排名 {datetime.now():%Y-%m-%d %H:%M:%S}")

    if not OHLCV_FILE.exists():
        print("❌ commodities_ohlcv.csv.gz 不存在")
        return

    df = pd.read_csv(OHLCV_FILE)
    df["date"] = pd.to_datetime(df["date"])
    print(f"📊 数据截止: {df['date'].max().date()}")

    predictor = load_predictor()
    results = []

    for sym, name in COMMODITIES.items():
        bt = time.time()
        print(f"   {sym} ({name})...", end=" ", flush=True)

        sub = df[df["symbol"] == sym]
        if sub.empty or len(sub) < 100:
            print(f"❌ 数据不足")
            continue

        close = sub["close"].tail(CTX_LEN + 100).values.astype(np.float64)
        current = float(close[-1])

        try:
            ds = gluonts_dataset(close)
            forecasts = list(predictor.predict(ds))
            if not forecasts:
                print("❌ 无预测")
                continue
            fc = forecasts[0]
            # 取中位数样本
            if hasattr(fc, 'samples'):
                samples = fc.samples  # (num_samples, horizon)
                median = np.median(samples, axis=0)
                low = np.percentile(samples, 10, axis=0)
                high = np.percentile(samples, 90, axis=0)
            else:
                median = fc.mean if hasattr(fc, 'mean') else np.array(fc.quantile(0.5))
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
