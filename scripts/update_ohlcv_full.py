#!/usr/bin/env python3
"""全量A股OHLCV增量更新 → ohlcv_full.csv.gz"""
import json, time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests as req

BASE = Path(__file__).resolve().parent.parent
OHLCV_FILE = BASE / "data/ohlcv_full.csv.gz"
NAME_MAP_FILE = BASE / "data/name_map.json"

NM = json.loads(NAME_MAP_FILE.read_text())
ALL_CODES = sorted(set(k for k in NM if k.isdigit() and len(k) == 6))
print(f"📊 全量股票池: {len(ALL_CODES)}只", flush=True)

existing = pd.DataFrame()
if OHLCV_FILE.exists():
    existing = pd.read_csv(OHLCV_FILE)
    existing["date"] = pd.to_datetime(existing["date"], format='ISO8601')
    print(f"   已有: {existing['code'].nunique()}只, {len(existing)}行, 截止{existing['date'].max().date()}")

last_date = existing["date"].max() if len(existing) > 0 else pd.Timestamp("2000-01-01")
today = pd.Timestamp.now().normalize()

if last_date >= today:
    print("✅ 已是最新")
    exit(0)

existing_codes = set(existing["code"].astype(str).str.zfill(6).unique()) if len(existing) > 0 else set()
new_rows = []
t0 = time.time()

for i, code in enumerate(ALL_CODES):
    sym = f"sh{code}" if code.startswith("6") else f"sz{code}"
    try:
        dl = 10 if code in existing_codes else 5000
        r = req.get(f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen={dl}", timeout=15)
        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            continue
        df = pd.DataFrame(data)
        df = df.rename(columns={"day": "date", "open": "open", "high": "high", "low": "low", "close": "close"})
        df["code"] = code
        df["date"] = pd.to_datetime(df["date"])
        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df[df["date"] > last_date]
        if len(df) > 0:
            new_rows.append(df[["date", "code", "open", "high", "low", "close"]].dropna())
    except Exception:
        pass
    if (i + 1) % 100 == 0 or i == 0:
        print(f"   [{i+1}/{len(ALL_CODES)}] {len(new_rows)}只有新数据, {(time.time()-t0)/60:.0f}min", flush=True)

if not new_rows:
    print("⚠️ 无新数据")
    exit(1)

new_df = pd.concat(new_rows, ignore_index=True)
combined = pd.concat([existing, new_df], ignore_index=True) if len(existing) > 0 else new_df
combined = combined.drop_duplicates(subset=["date", "code"]).sort_values(["code", "date"])
OHLCV_FILE.parent.mkdir(exist_ok=True)
combined.to_csv(OHLCV_FILE, index=False, compression="gzip")
print(f"✅ {len(ALL_CODES)}只, {len(combined)}行, 截止{combined['date'].max().date()}, {(time.time()-t0)/60:.0f}分钟")
