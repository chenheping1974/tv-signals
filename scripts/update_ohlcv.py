#!/usr/bin/env python3
"""本地Mac增量更新OHLCV（新浪财经） → push到GitHub"""
import json, time, sys, requests as req
import pandas as pd
from pathlib import Path
from datetime import datetime

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
print(f"   数据截止: {last_date.date()}")

if last_date >= pd.Timestamp(today):
    print("✅ 已是最新")
    sys.exit(0)

print(f"📥 新浪增量 ({last_date.date()} → {today})...")
codes = set(existing["code"].astype(str).str.zfill(6).unique())
new_rows, t0 = [], time.time()

for i, s in enumerate(pool):
    code = str(s["code"]).zfill(6)
    if code not in codes: continue
    sym = f"sh{code}" if code.startswith("6") else f"sz{code}"
    try:
        r = req.get(f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen=10", timeout=10)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)
            df = df.rename(columns={"day":"date","open":"open","high":"high","low":"low","close":"close"})
            df["code"] = code; df["date"] = pd.to_datetime(df["date"])
            for c in ["open","high","low","close"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df[df["date"] > last_date]
            if len(df) > 0:
                new_rows.append(df[["date","code","open","high","low","close"]].dropna())
    except: pass
    if i % 200 == 0:
        print(f"   [{i+1}/{len(pool)}] {len(new_rows)}只 {((time.time()-t0)/60):.1f}min")

if not new_rows:
    print("⚠️ 无新数据（可能市场休市）")
    sys.exit(0)

new_df = pd.concat(new_rows, ignore_index=True)
combined = pd.concat([existing, new_df], ignore_index=True)
combined = combined.drop_duplicates(subset=["date","code"]).sort_values(["code","date"])
combined.to_csv(OHLCV_FILE, index=False, compression="gzip")
print(f"✅ +{len(new_df)}行, 总计{len(combined)}行, 推送到GitHub...")

import subprocess
subprocess.run(["git", "-C", str(BASE), "add", "data/ohlcv.csv.gz"])
r = subprocess.run(["git", "-C", str(BASE), "commit", "-m", f"增量更新OHLCV [{today}]"])
if r.returncode == 0:
    subprocess.run(["git", "-C", str(BASE), "push"])
    print("🚀 完成")
