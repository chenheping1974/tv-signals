#!/usr/bin/env python3
"""本地Mac增量更新OHLCV → push到GitHub"""
import json, time, sys
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).resolve().parent.parent
OHLCV_FILE = BASE / "data/ohlcv.csv.gz"
POOL_FILE = BASE / "data/stock_pool.json"

print("📊 加载股票池...")
pool = json.loads(POOL_FILE.read_text())
if isinstance(pool, dict): pool = pool.get("stocks", pool)
print(f"   {len(pool)} 只")

existing = pd.read_csv(OHLCV_FILE)
existing["date"] = pd.to_datetime(existing["date"], format='ISO8601')
last_date = existing["date"].max()
today = datetime.now().date()
print(f"   现有数据截止: {last_date.date()}")

if last_date >= pd.Timestamp(today - timedelta(days=1)):
    print("✅ 已是最新, 无需更新")
    sys.exit(0)

print(f"📥 下载增量 ({last_date.date()} → {today})...")
codes = set(existing["code"].astype(str).str.zfill(6).unique())
new_rows, t0 = [], time.time()

for i, s in enumerate(pool):
    code = str(s["code"]).zfill(6)
    if code not in codes:
        continue
    sym = f"{code}.{'SS' if code.startswith('6') else 'SZ'}"
    try:
        df = yf.Ticker(sym).history(start=last_date + timedelta(days=1))
        if len(df) > 0:
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            df["code"] = code
            new_rows.append(df[["date","code","open","high","low","close"]].dropna())
    except: pass
    if i % 200 == 0:
        print(f"   [{i+1}/{len(pool)}] {len(new_rows)}只 {((time.time()-t0)/60):.1f}min")
    time.sleep(0.1)

if not new_rows:
    print("⚠️ 无新数据")
    sys.exit(0)

new_df = pd.concat(new_rows, ignore_index=True)
combined = pd.concat([existing, new_df], ignore_index=True)
combined = combined.drop_duplicates(subset=["date","code"]).sort_values(["code","date"])
combined.to_csv(OHLCV_FILE, index=False, compression="gzip")
print(f"✅ 更新完成: +{len(new_df)}行, 总计{len(combined)}行")

# Git push
import subprocess
subprocess.run(["git", "-C", str(BASE), "add", "data/ohlcv.csv.gz"])
subprocess.run(["git", "-C", str(BASE), "commit", "-m", f"增量更新OHLCV [{today}]"])
subprocess.run(["git", "-C", str(BASE), "push"])
print("🚀 已推送到GitHub")
