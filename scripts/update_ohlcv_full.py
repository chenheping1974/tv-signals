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

# 断点续传: 记录已下载到的位置
RESUME_FILE = BASE / "data/.ohlcv_full_resume"
resume_idx = 0
if RESUME_FILE.exists():
    try:
        resume_idx = int(RESUME_FILE.read_text().strip())
        print(f"📌 断点续传: 从第{resume_idx+1}只开始", flush=True)
    except:
        pass

existing_codes = set(existing["code"].astype(str).str.zfill(6).unique()) if len(existing) > 0 else set()
new_rows = []
t0 = time.time()
SAVE_EVERY = 500

for i in range(resume_idx, len(ALL_CODES)):
    code = ALL_CODES[i]
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

    # 定期存盘（仅存进度，最后统一合并）
    if (i + 1) % SAVE_EVERY == 0:
        RESUME_FILE.parent.mkdir(exist_ok=True)
        RESUME_FILE.write_text(str(i + 1))
        # 存临时增量到pickle，最后合并
        import pickle
        tmp = BASE / "data/.ohlcv_tmp.pkl"
        with open(tmp, "wb") as f:
            pickle.dump(new_rows, f)
        print(f"   [{i+1}/{len(ALL_CODES)}] {len(new_rows)}条增量, {(time.time()-t0)/60:.0f}min", flush=True)

# 清理断点
if RESUME_FILE.exists():
    RESUME_FILE.unlink()

# 最终合并
if new_rows:
    batch = pd.concat(new_rows, ignore_index=True)
    combined = pd.concat([existing, batch], ignore_index=True) if len(existing) > 0 else batch
    combined = combined.drop_duplicates(subset=["date", "code"]).sort_values(["code", "date"])
    OHLCV_FILE.parent.mkdir(exist_ok=True)
    combined.to_csv(OHLCV_FILE, index=False, compression="gzip")

tmp = BASE / "data/.ohlcv_tmp.pkl"
if tmp.exists():
    tmp.unlink()

if not OHLCV_FILE.exists():
    print("❌ 无数据", flush=True)
    exit(1)

df_final = pd.read_csv(OHLCV_FILE)
df_final["date"] = pd.to_datetime(df_final["date"])
print(f"✅ {df_final['code'].nunique()}只, {len(df_final)}行, 截止{df_final['date'].max().date()}, {(time.time()-t0)/60:.0f}分钟", flush=True)
